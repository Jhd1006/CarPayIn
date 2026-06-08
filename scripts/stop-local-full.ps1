##############################################################################
# stop-local-full.ps1  -  Car Pay In local stack shutdown
#
# Flags:
#   -Down         docker compose down (remove containers, keep volumes)
#   -DownVolumes  docker compose down -v (remove containers + volumes = DB reset)
#   -KeepNgrok    skip ngrok shutdown
##############################################################################
param(
    [switch] $Down,
    [switch] $DownVolumes,
    [switch] $KeepNgrok
)

$ErrorActionPreference = "Continue"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot

function Step([string]$msg) { Write-Host ""; Write-Host ">>> $msg" -ForegroundColor Cyan }
function OK([string]$msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function WARN([string]$msg) { Write-Host "  [!!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Car Pay In - Stop local stack" -ForegroundColor Cyan
Write-Host "================================================================"

# ── 1. Log windows (cmd /k docker compose logs ...) ──────────────────────
Step "1/5  Close log windows"
$logProcs = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
    Where-Object { $_.CommandLine -match "docker\s+compose\s+logs" }
if ($logProcs) {
    $logProcs | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    OK "$($logProcs.Count) log window(s) closed"
} else {
    OK "No log windows found"
}

# ── 2. GPS Proxy (port 5600) ──────────────────────────────────────────────
Step "2/5  Stop GPS Proxy (:5600)"
$port5600Lines = netstat -ano 2>$null | Select-String ":5600\s" | Select-String "LISTENING"
if ($port5600Lines) {
    $pidList = $port5600Lines | ForEach-Object {
        ($_.Line -split '\s+') | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
    }
    $pidList | Sort-Object -Unique | ForEach-Object {
        $p = [int]$_
        if ($p -gt 0) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            OK "PID $p stopped (GPS proxy)"
        }
    }
} else {
    OK "GPS proxy not running"
}
# Clean up PS jobs
Get-Job -ErrorAction SilentlyContinue |
    Where-Object { $_.Command -match "gps_proxy" } |
    ForEach-Object { Stop-Job $_ -ErrorAction SilentlyContinue; Remove-Job $_ -ErrorAction SilentlyContinue }

# ── 3. ngrok ──────────────────────────────────────────────────────────────
Step "3/5  Stop ngrok"
if (-not $KeepNgrok) {
    $ngrokProcs = Get-Process ngrok -ErrorAction SilentlyContinue
    if ($ngrokProcs) {
        $ngrokProcs | Stop-Process -Force -ErrorAction SilentlyContinue
        OK "ngrok stopped"
    } else {
        OK "ngrok not running"
    }
} else {
    WARN "-KeepNgrok: skipping ngrok"
}

# ── 4. Docker Compose ─────────────────────────────────────────────────────
Step "4/5  Docker Compose"
if ($DownVolumes) {
    Write-Host "  docker compose down -v  (removes containers + volumes)"
    docker compose down -v
    OK "Containers + volumes removed"
} elseif ($Down) {
    Write-Host "  docker compose down  (removes containers, keeps volumes)"
    docker compose down
    OK "Containers removed"
} else {
    Write-Host "  docker compose stop  (stops containers, data preserved)"
    docker compose stop
    OK "Services stopped  (restart: docker compose start)"
}

# ── 5. Status ─────────────────────────────────────────────────────────────
Step "5/5  Final status"
$running = docker compose ps -q 2>$null | Where-Object { $_ -ne "" }
if ($running) {
    WARN "Still running: $($running -join ', ')"
} else {
    OK "All services stopped"
}

Pop-Location
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Done." -ForegroundColor Cyan
Write-Host "================================================================"
Write-Host ""
Write-Host "  To restart (no rebuild):" -ForegroundColor Yellow
Write-Host '    powershell -ExecutionPolicy Bypass -File scripts\start-local-full.ps1 -NoRebuild'
Write-Host ""
