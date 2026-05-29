param(
    [switch] $Down,
    [switch] $KeepNgrok
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $Root "docker-compose.yaml"
Set-Location $Root

Write-Host ""
Write-Host "==> Stopping Docker Compose services" -ForegroundColor Cyan
if ($Down) {
    docker compose -f $ComposeFile down
} else {
    docker compose -f $ComposeFile stop
}
if ($LASTEXITCODE -ne 0) {
    throw "docker compose stop/down failed with exit code $LASTEXITCODE"
}

if (-not $KeepNgrok) {
    Write-Host ""
    Write-Host "==> Stopping ngrok processes" -ForegroundColor Cyan
    $processes = Get-Process ngrok -ErrorAction SilentlyContinue
    if ($processes) {
        $processes | Stop-Process -Force
        Write-Host "OK  ngrok stopped" -ForegroundColor Green
    } else {
        Write-Host "OK  no ngrok process found" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Done."
