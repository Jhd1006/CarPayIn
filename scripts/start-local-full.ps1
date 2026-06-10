##############################################################################
# start-local-full.ps1  -  Car Pay In full LOCAL test stack launcher
#
# Starts everything needed for local E2E testing (without Webots):
#   ngrok         -> Hyundai OAuth callback
#   Docker Compose -> backend / pms / mock-pg / mock-card / redis / mqtt
#   Android        -> updates local.properties for AAOS emulator
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\start-local-full.ps1
#
# Flags:
#   -NoRebuild    Skip Docker image rebuild
#   -NotebookIp   Override auto-detected LAN IP
##############################################################################
param(
    [string] $NotebookIp = "",
    [switch] $NoRebuild
)

$ErrorActionPreference = "Stop"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = Resolve-Path (Join-Path $ScriptDir "..")
$EnvFile     = Join-Path $RepoRoot ".env"
$LocalProps  = Join-Path $RepoRoot "services\android-app\local.properties"
$BackendPort = 8000

# ── helpers ──────────────────────────────────────────────────────────────────
function Step([string]$msg)  { Write-Host ""; Write-Host ">>> $msg" -ForegroundColor Cyan }
function OK([string]$msg)    { Write-Host "  [OK] $msg"   -ForegroundColor Green  }
function WARN([string]$msg)  { Write-Host "  [!!] $msg"   -ForegroundColor Yellow }
function INFO([string]$msg)  { Write-Host "       $msg" }

function Get-LanIp {
    $cfgs = Get-NetIPConfiguration |
        Where-Object {
            $_.IPv4Address -and $_.IPv4DefaultGateway -and
            $_.NetAdapter.Status -eq "Up" -and
            $_.NetAdapter.InterfaceDescription -notmatch "Virtual|Hyper-V|VMware|VirtualBox|Loopback"
        }
    foreach ($c in $cfgs) {
        foreach ($a in $c.IPv4Address) {
            if ($a.IPAddress -and $a.IPAddress -notmatch "^(127|169\.254)\.") { return $a.IPAddress }
        }
    }
    return (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notmatch "^(127|169\.254)" -and $_.PrefixOrigin -ne "WellKnown" } |
        Select-Object -First 1).IPAddress
}

function Wait-Http([string]$label, [string]$url, [int]$sec = 90) {
    Write-Host ("  Waiting " + $label) -NoNewline
    for ($i = 0; $i -lt $sec; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -lt 400) { Write-Host " OK" -ForegroundColor Green; return $true }
        } catch {}
        Start-Sleep 1
        if ($i % 5 -eq 4) { Write-Host "." -NoNewline }
    }
    Write-Host " TIMEOUT" -ForegroundColor Yellow
    WARN "$label not responding at $url"
    return $false
}

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Set-EnvKey([string]$path, [string]$key, [string]$value) {
    $lines = if (Test-Path $path) { [System.IO.File]::ReadAllLines($path, $Utf8NoBom) } else { @() }
    $found = $false
    $esc   = [regex]::Escape($key)
    $out   = [System.Collections.Generic.List[string]]::new()
    foreach ($l in $lines) {
        if ($l -match "^\s*$esc\s*=") { $found = $true; $out.Add("$key=$value") }
        else { $out.Add($l) }
    }
    if (-not $found) { $out.Add("$key=$value") }
    [System.IO.File]::WriteAllLines($path, $out, $Utf8NoBom)
}

function Get-NgrokUrl {
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
        $t = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($t) { return $t.public_url.TrimEnd("/") }
    } catch {}
    return ""
}

# ── 0. Firewall ───────────────────────────────────────────────────────────────
$fwPorts  = @(8000, 8001, 8002, 8003, 1883)
$fwRule   = Get-NetFirewallRule -DisplayName "CarPayIn-Local" -ErrorAction SilentlyContinue
$fwPorted = if ($fwRule) { ($fwRule | Get-NetFirewallPortFilter).LocalPort } else { @() }
$missing  = $fwPorts | Where-Object { $_ -notin $fwPorted }
if ($missing) {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) {
        Remove-NetFirewallRule -DisplayName "CarPayIn-Local" -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName "CarPayIn-Local" -Direction Inbound -Protocol TCP `
            -LocalPort $fwPorts -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
        OK "Firewall: CarPayIn-Local updated (ports $($fwPorts -join ','))"
    } else {
        Start-Process powershell -Verb RunAs -ArgumentList @(
            "-NoProfile", "-Command",
            "Remove-NetFirewallRule -DisplayName 'CarPayIn-Local' -EA SilentlyContinue; New-NetFirewallRule -DisplayName 'CarPayIn-Local' -Direction Inbound -Protocol TCP -LocalPort @($($fwPorts -join ',')) -Action Allow -Profile Any | Out-Null"
        ) -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        OK "Firewall: UAC prompt sent to update ports"
    }
} else {
    OK "Firewall: CarPayIn-Local OK (ports $($fwPorts -join ','))"
}

# ── 0b. Docker Desktop ───────────────────────────────────────────────────────
Step "0/6  Docker Desktop"
$dockerOk = $false
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    # Docker Desktop 경로 후보
    $dockerDesktopExe = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\Docker\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($dockerDesktopExe) {
        INFO "Docker not running. Starting Docker Desktop..."
        Start-Process -FilePath $dockerDesktopExe
        Write-Host "  Waiting for Docker engine" -NoNewline
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep 2
            Write-Host "." -NoNewline
            try {
                docker info 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
            } catch {}
        }
        Write-Host ""
        if ($dockerOk) { OK "Docker Desktop started" }
        else { throw "Docker Desktop did not start in time. Launch it manually and re-run." }
    } else {
        throw "Docker is not running and Docker Desktop.exe was not found. Start Docker Desktop manually and re-run."
    }
} else {
    OK "Docker Desktop already running"
}

# ── 1. Detect notebook LAN IP ────────────────────────────────────────────────
Step "1/6  Detect notebook LAN IP"
if (-not $NotebookIp) { $NotebookIp = Get-LanIp }
if (-not $NotebookIp) { throw "Cannot detect IP. Re-run with -NotebookIp 192.168.x.x" }
OK "Notebook IP: $NotebookIp"

# ── 2. ngrok ─────────────────────────────────────────────────────────────────
Step "2/6  ngrok (Hyundai OAuth callback)"
$ngrokUrl = Get-NgrokUrl
if ($ngrokUrl) {
    OK "ngrok already running: $ngrokUrl"
} else {
    $ngrokCmd = Get-Command ngrok -ErrorAction SilentlyContinue
    $ngrokExe = if ($ngrokCmd) { $ngrokCmd.Source } else { $null }
    if (-not $ngrokExe) {
        WARN "ngrok not found. Install ngrok and re-run, or set NGROK_EXE env var."
        WARN "Hyundai OAuth will not work without ngrok."
    } else {
        Start-Process -FilePath $ngrokExe -ArgumentList @("http", "$BackendPort") -WindowStyle Normal
        Write-Host "  ngrok starting" -NoNewline
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Seconds 1
            Write-Host "." -NoNewline
            $ngrokUrl = Get-NgrokUrl
            if ($ngrokUrl) { break }
        }
        Write-Host ""
        if ($ngrokUrl) { OK "ngrok tunnel: $ngrokUrl" }
        else { WARN "ngrok did not start. Check the ngrok window - auth token may be needed: ngrok config add-authtoken <token>" }
    }
}

# ── 3. Patch .env ────────────────────────────────────────────────────────────
Step "3/6  Patch .env"
Set-EnvKey $EnvFile "PMS_DATABASE_URL"       "postgresql+psycopg://dev_user:dev_pass@pms-postgres:5432/pms_dev"
Set-EnvKey $EnvFile "MOCK_PG_DATABASE_URL"   "postgresql+psycopg://dev_user:dev_pass@mock-pg-postgres:5432/mock_pg_dev"
# 서비스 내부 URL: Docker 네트워크 내 컨테이너명으로 통신
Set-EnvKey $EnvFile "PG_BASE_URL"            "http://mock-pg:8000"
Set-EnvKey $EnvFile "PMS_BASE_URL"           "http://pms:8000"
Set-EnvKey $EnvFile "MOCK_CARD_BASE_URL"     "http://mock-card:8000"
Set-EnvKey $EnvFile "CARPAYIN_BACKEND_BASE_URL" "http://carpayin-backend:8000"
# PG_PUBLIC_BASE_URL: Android 에뮬레이터에서 접근 가능한 mock-pg 주소
Set-EnvKey $EnvFile "PG_PUBLIC_BASE_URL"     "http://10.0.2.2:8002"
if ($ngrokUrl) {
    Set-EnvKey $EnvFile "PUBLIC_BASE_URL" $ngrokUrl
    OK ".env: PUBLIC_BASE_URL=$ngrokUrl"
}
OK ".env: service URLs patched"

# ── 4. Docker Compose up ──────────────────────────────────────────────────────
Step "4/6  Docker Compose up"
Push-Location $RepoRoot
try {
    $composeArgs = @("compose", "up", "-d")
    if (-not $NoRebuild) {
        INFO "Building images (skip with -NoRebuild)"
        $composeArgs += "--build"
    }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}
OK "Docker Compose started"

# ── 5. Wait for services ─────────────────────────────────────────────────────
Step "5/6  Wait for services"
$backendOk  = Wait-Http "Backend   :8000" "http://localhost:8000/health"
$pmsOk      = Wait-Http "PMS       :8001" "http://localhost:8001/health"
$mockPgOk   = Wait-Http "Mock-PG   :8002" "http://localhost:8002/health"
$mockCardOk = Wait-Http "Mock-Card :8003" "http://localhost:8003/health"

# MQTT는 HTTP가 아니므로 TCP 연결로 확인
Write-Host "  Waiting MQTT      :1883" -NoNewline
$mqttOk = $false
for ($i = 0; $i -lt 30; $i++) {
    $t = Test-NetConnection -ComputerName localhost -Port 1883 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    if ($t.TcpTestSucceeded) { Write-Host " OK" -ForegroundColor Green; $mqttOk = $true; break }
    Start-Sleep 1
    if ($i % 5 -eq 4) { Write-Host "." -NoNewline }
}
if (-not $mqttOk) { Write-Host " TIMEOUT" -ForegroundColor Yellow }

# ── 6. Android local.properties ──────────────────────────────────────────────
Step "6/6  Android local.properties"
if (-not (Test-Path $LocalProps)) {
    Copy-Item (Join-Path $RepoRoot "services\android-app\local.properties.example") $LocalProps
    INFO "Created local.properties from example"
}
Set-EnvKey $LocalProps "CARPAYIN_BACKEND_BASE_URL"           "http://10.0.2.2:$BackendPort"
Set-EnvKey $LocalProps "CARPAYIN_MQTT_BROKER_URL"            "tcp://10.0.2.2:1883"
Set-EnvKey $LocalProps "CARPAYIN_EMULATOR_LOCALHOST_REWRITE" "true"
if ($ngrokUrl) {
    Set-EnvKey $LocalProps "CARPAYIN_QR_BASE_URL" $ngrokUrl
    OK "local.properties: backend=10.0.2.2:8000, MQTT=10.0.2.2:1883, QR=$ngrokUrl"
} else {
    OK "local.properties: backend=10.0.2.2:8000, MQTT=10.0.2.2:1883 (QR URL not updated, ngrok not running)"
}

# Android emulator 감지
$adb = Get-Command adb -ErrorAction SilentlyContinue
if ($adb) {
    $devs = adb devices 2>&1 | Where-Object { $_ -match "emulator|device$" }
    if ($devs) { OK "Android emulator: $devs" }
    else { WARN "Android emulator not detected - start AAOS emulator before running the app" }
} else {
    WARN "adb not in PATH - cannot check emulator status"
}

# ── Log windows ──────────────────────────────────────────────────────────────
$services = @(
    @{ name = "Backend  :8000"; svc = "carpayin-backend" },
    @{ name = "Mock-PMS :8001"; svc = "pms"             },
    @{ name = "Mock-PG  :8002"; svc = "mock-pg"         },
    @{ name = "Mock-Card:8003"; svc = "mock-card"       },
    @{ name = "MQTT     :1883"; svc = "mqtt"            }
)
Push-Location $RepoRoot
foreach ($s in $services) {
    Start-Process cmd -ArgumentList "/k docker compose logs -f $($s.svc)" `
        -WindowStyle Normal
}
Pop-Location
OK "Log windows opened for all services"

# ── Summary ───────────────────────────────────────────────────────────────────
$ok  = "[OK] "
$err = "[!!] "
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Car Pay In - LOCAL test stack ready" -ForegroundColor Cyan
Write-Host "================================================================"
Write-Host ""
Write-Host "  Services:"
Write-Host ("    Backend   " + $(if ($backendOk)  { $ok } else { $err }) + "http://localhost:8000")
Write-Host ("    PMS       " + $(if ($pmsOk)      { $ok } else { $err }) + "http://localhost:8001")
Write-Host ("    Mock-PG   " + $(if ($mockPgOk)   { $ok } else { $err }) + "http://localhost:8002")
Write-Host ("    Mock-Card " + $(if ($mockCardOk) { $ok } else { $err }) + "http://localhost:8003")
Write-Host ("    MQTT      " + $(if ($mqttOk) { $ok } else { $err }) + "tcp://localhost:1883  (emulator: tcp://10.0.2.2:1883)")
if ($ngrokUrl) {
    Write-Host "    ngrok      $ngrokUrl"
}
Write-Host ""
if ($ngrokUrl) {
    Write-Host "  Hyundai Developer Center - register these URLs:" -ForegroundColor Yellow
    Write-Host "    Redirect URI  : $ngrokUrl/auth/redirect"
    Write-Host "    Data Agreement: $ngrokUrl/auth/data-agreement/redirect"
    Write-Host "    Data Callback : $ngrokUrl/data/callback"
    Write-Host ""
}
Write-Host "  Test flow:"
Write-Host "    1) Run CarPayIn app on AAOS emulator"
Write-Host "    2) QR login -> vehicle confirmation -> card registration"
Write-Host "    3) Select parking lot -> tap navigation button (사전 입차 등록)"
Write-Host "    4) Trigger LPR: POST http://localhost:8001/lpr/entry"
Write-Host "    5) App receives entry notification (parked=true)"
Write-Host "    6) App shows fee -> approve payment -> auto payment"
Write-Host "    7) Trigger exit LPR: POST http://localhost:8001/lpr/exit"
Write-Host ""
Write-Host "  API docs:"
Write-Host "    http://localhost:8000/docs   (Backend)"
Write-Host "    http://localhost:8001/docs   (PMS)"
Write-Host "    http://localhost:8002/docs   (Mock-PG)"
Write-Host "    http://localhost:8003/docs   (Mock-Card)"
Write-Host "================================================================"
