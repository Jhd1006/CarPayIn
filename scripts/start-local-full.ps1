##############################################################################
# start-local-full.ps1  -  Car Pay In full LOCAL test stack launcher
#
# Starts everything needed for local E2E testing:
#   ngrok -> Hyundai OAuth callback
#   Docker Compose -> backend / pms / mock-pg / mock-card / redis / mqtt
#   GPS proxy window -> Webots GPS injection to Android emulator
#   Webots deploy (optional) -> Ubuntu desktop
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\start-local-full.ps1
#
# Flags:
#   -NoRebuild    Skip Docker image rebuild
#   -NoWebots     Skip Ubuntu Webots deploy
#   -NotebookIp   Override auto-detected LAN IP
#   -UbuntuRemote SSH target (default: homeless@192.168.200.201)
##############################################################################
param(
    [string] $NotebookIp   = "",
    [string] $UbuntuRemote = "homeless@192.168.200.201",
    [switch] $NoRebuild,
    [switch] $NoWebots
)

$ErrorActionPreference = "Stop"
$ScriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot       = Resolve-Path (Join-Path $ScriptDir "..")
$EnvFile        = Join-Path $RepoRoot ".env"
$WebotsEnv      = Join-Path $RepoRoot "services\webots\.env"
$GpsProxy       = Join-Path $RepoRoot "services\webots\gps_proxy.py"
$LocalProps     = Join-Path $RepoRoot "services\android-app\local.properties"
$WebotsZip      = "C:\Users\USER\Desktop\Car Pay In\carpayin-webots-patched.zip"
$ResetPs1       = "C:\Users\USER\Desktop\Car Pay In\reset_and_reinstall_webots_clean.ps1"
$BackendPort    = 8000

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

function Find-Python {
    if (Get-Command py     -ErrorAction SilentlyContinue) { return @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
    throw "Python not found. Add python or py to PATH."
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
$fwPorts  = @(8000, 8001, 8002, 8003, 5600, 1883)
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

# ── 1. Detect notebook LAN IP ────────────────────────────────────────────────
Step "1/8  Detect notebook LAN IP"
if (-not $NotebookIp) { $NotebookIp = Get-LanIp }
if (-not $NotebookIp) { throw "Cannot detect IP. Re-run with -NotebookIp 192.168.x.x" }
OK "Notebook IP: $NotebookIp"

# ── 2. ngrok ─────────────────────────────────────────────────────────────────
Step "2/8  ngrok (Hyundai OAuth callback)"
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
Step "3/8  Patch .env"
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
OK ".env: local DB URLs set"

# ── 4. Write webots .env ──────────────────────────────────────────────────────
Step "4/8  Write services\webots\.env"
$plate = [System.Text.Encoding]::UTF8.GetString([byte[]]@(49,50,51,234,176,128,52,53,54,55))
$webotsContent = "# Auto-generated by start-local-full.ps1`n" +
    "CARPAYIN_NOTEBOOK_IP=$NotebookIp`n" +
    "BACKEND_URL=http://${NotebookIp}:8000`n" +
    "PARKING_PMS_URL=http://${NotebookIp}:8001`n" +
    "GPS_PROXY_URL=http://${NotebookIp}:5600`n" +
    "ADB_HOST=$NotebookIp`n`n" +
    "WEBOTS_VIN=TESTVIN001`n" +
    "WEBOTS_PLATE=$plate`n" +
    "WEBOTS_LOT_ID=LOT_TEST_01`n"
[System.IO.File]::WriteAllText($WebotsEnv, $webotsContent, $Utf8NoBom)
OK "Webots .env written"

# ── 5. Docker Compose up ──────────────────────────────────────────────────────
Step "5/8  Docker Compose up"
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

# ── 6. Wait for services ─────────────────────────────────────────────────────
Step "6/8  Wait for services"
$backendOk  = Wait-Http "Backend   :8000" "http://localhost:8000/health"
$pmsOk      = Wait-Http "PMS       :8001" "http://localhost:8001/openapi.json"
$mockPgOk   = Wait-Http "Mock-PG   :8002" "http://localhost:8002/openapi.json"
$mockCardOk = Wait-Http "Mock-Card :8003" "http://localhost:8003/openapi.json"

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

try {
    Invoke-WebRequest -Uri "http://localhost:8000/sim/location" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop | Out-Null
    OK "/sim/location endpoint OK"
} catch {
    WARN "/sim/location 404 - backend image outdated. Re-run without -NoRebuild."
}

# ── 7. Android local.properties ──────────────────────────────────────────────
Step "7/8  Android local.properties"
if (-not (Test-Path $LocalProps)) {
    Copy-Item (Join-Path $RepoRoot "services\android-app\local.properties.example") $LocalProps
    INFO "Created local.properties from example"
}
Set-EnvKey $LocalProps "CARPAYIN_BACKEND_BASE_URL"          "http://10.0.2.2:$BackendPort"
Set-EnvKey $LocalProps "CARPAYIN_MQTT_BROKER_URL"           "tcp://10.0.2.2:1883"
Set-EnvKey $LocalProps "CARPAYIN_EMULATOR_LOCALHOST_REWRITE" "true"
if ($ngrokUrl) {
    Set-EnvKey $LocalProps "CARPAYIN_QR_BASE_URL" $ngrokUrl
    OK "local.properties: backend=10.0.2.2:8000, QR=$ngrokUrl"
} else {
    OK "local.properties: backend=10.0.2.2:8000 (QR URL not updated, ngrok not running)"
}

# ── GPS proxy ─────────────────────────────────────────────────────────────────
Step "GPS proxy (port 5600)"
$port5600 = netstat -ano 2>$null | Select-String ":5600 " | Select-String "LISTENING"
if ($port5600) {
    OK "GPS proxy already running on port 5600"
} else {
    $pyCmd   = Find-Python
    $pyExe   = $pyCmd[0]
    $pyArgs  = if ($pyCmd.Length -gt 1) { $pyCmd[1..($pyCmd.Length-1)] } else { @() }
    $allArgs = $pyArgs + @($GpsProxy)
    $gpsJob  = Start-Job -ScriptBlock { param($e,$a) & $e @a } -ArgumentList $pyExe,$allArgs
    Start-Sleep -Seconds 3
    $check = netstat -ano 2>$null | Select-String ":5600 " | Select-String "LISTENING"
    if ($check) { OK "GPS proxy running (job $($gpsJob.Id))" }
    else {
        WARN "GPS proxy failed. Start manually: python `"$GpsProxy`""
    }
}

# ── 8. Webots ─────────────────────────────────────────────────────────────────
Step "8/8  Webots deploy (Ubuntu)"
if ($NoWebots) {
    WARN "-NoWebots flag set, skipping"
} elseif (-not (Test-Path $ResetPs1) -or -not (Test-Path $WebotsZip)) {
    WARN "Webots zip or reset script not found, skipping"
} else {
    INFO "Deploying to Ubuntu ($UbuntuRemote) ..."
    & powershell -ExecutionPolicy Bypass -File $ResetPs1 -Remote $UbuntuRemote -NotebookIp $NotebookIp
    if ($LASTEXITCODE -eq 0) { OK "Webots deployed" }
    else { WARN "Webots deploy failed. Run reset script manually." }
}

# ADB check
$adb = Get-Command adb -ErrorAction SilentlyContinue
if ($adb) {
    $devs = adb devices 2>&1 | Where-Object { $_ -match "emulator|device$" }
    if ($devs) { OK "Android emulator: $devs" }
    else { WARN "Android emulator not detected - start AAOS emulator first" }
} else {
    WARN "adb not in PATH"
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
Write-Host "    GPS Proxy  http://${NotebookIp}:5600"
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
Write-Host "    1) Launch 'CarPayIn Webots' on Ubuntu desktop"
Write-Host "    2) Run CarPayIn app on AAOS emulator"
Write-Host "    3) QR login -> card registration"
Write-Host "    4) Select parking lot -> navigation"
Write-Host "    5) Arrow keys in Webots -> drive to parking -> LPR"
Write-Host "    6) Payment notification -> auto payment"
Write-Host ""
Write-Host "  Logs:"
Write-Host "    docker compose logs -f carpayin-backend"
Write-Host "    docker compose logs -f pms"
Write-Host "    ssh $UbuntuRemote 'tail -f /tmp/carpayin_vehicle_driver.log'"
Write-Host "================================================================"
