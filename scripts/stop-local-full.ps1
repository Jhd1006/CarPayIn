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
Step "1/3  Close log windows"
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

# ── 2. ngrok ──────────────────────────────────────────────────────────────
Step "2/3  Stop ngrok"
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

# ── 3. Docker Compose ─────────────────────────────────────────────────────
Step "3/3  Docker Compose"
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

# ── Status ─────────────────────────────────────────────────────────────
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
Write-Host "  To reset all DB data:" -ForegroundColor Yellow
Write-Host '    powershell -ExecutionPolicy Bypass -File scripts\stop-local-full.ps1 -DownVolumes'
Write-Host ""
