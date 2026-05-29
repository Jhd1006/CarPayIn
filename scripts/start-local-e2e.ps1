param(
    [switch] $NoDocker,
    [switch] $NoNgrok,
    [switch] $NoRebuild,
    [switch] $DryRun,
    [switch] $AllowDynamicNgrok,
    [int] $BackendPort = 8000,
    [string] $PublicBaseUrl = "",
    [string] $NgrokExe = $env:NGROK_EXE
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $Root "docker-compose.yaml"
$EnvFile = Join-Path $Root ".env"
$EnvExampleFile = Join-Path $Root ".env.example"
$AndroidLocalProperties = Join-Path $Root "services\android-app\local.properties"

function Write-Step([string] $Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string] $Message) {
    Write-Host "OK  $Message" -ForegroundColor Green
}

function Write-Warn([string] $Message) {
    Write-Host "WARN $Message" -ForegroundColor Yellow
}

function Invoke-Checked([string] $FilePath, [string[]] $ArgumentList, [string] $WorkingDirectory = $Root) {
    $command = "$FilePath $($ArgumentList -join ' ')"
    if ($DryRun) {
        Write-Host "[dry-run] $command"
        return
    }

    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $command"
        }
    } finally {
        Pop-Location
    }
}

function Read-DotEnv([string] $Path) {
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $key, $value = $trimmed.Split("=", 2)
        $values[$key.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $values
}

function Set-DotEnvValue([string] $Path, [string] $Key, [string] $Value) {
    $lines = @()
    if (Test-Path -LiteralPath $Path) {
        $lines = @(Get-Content -LiteralPath $Path)
    }

    $found = $false
    $escapedKey = [regex]::Escape($Key)
    $next = foreach ($line in $lines) {
        if ($line -match "^\s*$escapedKey\s*=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }

    if (-not $found) {
        $next += "$Key=$Value"
    }

    if ($DryRun) {
        Write-Host "[dry-run] set $Key in $Path"
        return
    }
    Set-Content -LiteralPath $Path -Value $next -Encoding UTF8
}

function Get-EnvValue([hashtable] $Values, [string] $Key, [string] $Default = "") {
    if ($Values.ContainsKey($Key) -and $Values[$Key]) {
        return $Values[$Key]
    }
    return $Default
}

function Test-Placeholder([string] $Value) {
    return [string]::IsNullOrWhiteSpace($Value) -or
        $Value -match "your-" -or
        $Value -match "hyundai-dev" -or
        $Value -match "hyundai-client-001"
}

function Find-NgrokExe([string] $RequestedPath) {
    if ($RequestedPath -and (Test-Path -LiteralPath $RequestedPath)) {
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }

    $cmd = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return ""
}

function Get-NgrokPublicUrl() {
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
        $httpsTunnel = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($httpsTunnel) {
            return $httpsTunnel.public_url.TrimEnd("/")
        }
    } catch {
        return ""
    }
    return ""
}

function Get-NgrokStaticArg([string] $NgrokPath, [string] $Url) {
    if ([string]::IsNullOrWhiteSpace($Url) -or $Url -match "your-ngrok-domain") {
        return @()
    }

    $uri = [Uri] $Url
    $hostName = $uri.Host
    $help = ""
    try {
        $help = & $NgrokPath http --help 2>&1 | Out-String
    } catch {
        return @()
    }

    if ($help -match "--url") {
        return @("--url=$hostName")
    }
    if ($help -match "--domain") {
        return @("--domain=$hostName")
    }
    if ($help -match "--hostname") {
        return @("--hostname=$hostName")
    }

    return @()
}

function Ensure-EnvFile() {
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        if (Test-Path -LiteralPath $EnvExampleFile) {
            if ($DryRun) {
                Write-Host "[dry-run] copy $EnvExampleFile to $EnvFile"
            } else {
                Copy-Item -LiteralPath $EnvExampleFile -Destination $EnvFile
            }
            Write-Warn ".env was created from .env.example. Fill HYUNDAI_CLIENT_ID and HYUNDAI_CLIENT_SECRET before real Hyundai OAuth."
        } else {
            if (-not $DryRun) {
                New-Item -Path $EnvFile -ItemType File -Force | Out-Null
            }
            Write-Warn ".env was created. Fill Hyundai values before real OAuth."
        }
    }
}

function Update-AndroidLocalProperties([string] $Url) {
    if (-not (Test-Path -LiteralPath $AndroidLocalProperties)) {
        Write-Warn "Android local.properties not found. Skipping Android URL update."
        return
    }

    Set-DotEnvValue -Path $AndroidLocalProperties -Key "CARPAYIN_BACKEND_BASE_URL" -Value "http://10.0.2.2:$BackendPort"
    if (-not [string]::IsNullOrWhiteSpace($Url)) {
        Set-DotEnvValue -Path $AndroidLocalProperties -Key "CARPAYIN_QR_BASE_URL" -Value $Url
    }
    Set-DotEnvValue -Path $AndroidLocalProperties -Key "CARPAYIN_EMULATOR_LOCALHOST_REWRITE" -Value "true"
}

function Start-NgrokIfNeeded([string] $DesiredPublicUrl) {
    if ($NoNgrok) {
        Write-Warn "Skipping ngrok because -NoNgrok was passed."
        return $DesiredPublicUrl
    }

    $existingUrl = Get-NgrokPublicUrl
    if ($existingUrl) {
        Write-Ok "ngrok is already running: $existingUrl"
        if ($DesiredPublicUrl -and $DesiredPublicUrl -notmatch "your-ngrok-domain" -and $existingUrl -ne $DesiredPublicUrl) {
            if (-not $AllowDynamicNgrok) {
                throw "ngrok URL ($existingUrl) does not match PUBLIC_BASE_URL ($DesiredPublicUrl). Stop ngrok or pass -AllowDynamicNgrok."
            }
            Write-Warn "Using dynamic ngrok URL. Hyundai developer center Redirect URL must match it."
            return $existingUrl
        }
        return $existingUrl
    }

    $ngrok = Find-NgrokExe $NgrokExe
    if (-not $ngrok) {
        throw "ngrok.exe was not found. Install ngrok, add it to PATH, or run: set NGROK_EXE=C:\path\to\ngrok.exe"
    }

    $args = @("http")
    $staticArg = Get-NgrokStaticArg -NgrokPath $ngrok -Url $DesiredPublicUrl
    if ($staticArg.Count -gt 0) {
        $args += $staticArg
    } elseif ($DesiredPublicUrl -and $DesiredPublicUrl -notmatch "your-ngrok-domain") {
        Write-Warn "This ngrok version did not advertise --url/--domain/--hostname. Starting a dynamic tunnel."
    }
    $args += @($BackendPort.ToString())

    Write-Step "Starting ngrok: $ngrok $($args -join ' ')"
    if (-not $DryRun) {
        Start-Process -FilePath $ngrok -ArgumentList $args -WindowStyle Hidden | Out-Null
    }

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $url = Get-NgrokPublicUrl
        if ($url) {
            Write-Ok "ngrok tunnel is ready: $url"
            if ($DesiredPublicUrl -and $DesiredPublicUrl -notmatch "your-ngrok-domain" -and $url -ne $DesiredPublicUrl) {
                if (-not $AllowDynamicNgrok) {
                    throw "ngrok URL ($url) does not match PUBLIC_BASE_URL ($DesiredPublicUrl). Hyundai developer center must match exactly."
                }
                Write-Warn "Using dynamic ngrok URL. Hyundai developer center Redirect URL must match it."
            }
            return $url
        }
    }

    throw "ngrok did not expose a tunnel on http://127.0.0.1:4040 within 30 seconds."
}

function Wait-HttpOk([string] $Name, [string] $Url) {
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Ok "$Name is ready: $Url"
                return
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "$Name did not become ready: $Url"
}

Write-Step "Preparing local E2E environment"
Set-Location $Root
Ensure-EnvFile

$envValues = Read-DotEnv $EnvFile
$desiredPublicUrl = $PublicBaseUrl
if (-not $desiredPublicUrl) {
    $desiredPublicUrl = Get-EnvValue $envValues "PUBLIC_BASE_URL" ""
}
$desiredPublicUrl = $desiredPublicUrl.TrimEnd("/")

$clientId = Get-EnvValue $envValues "HYUNDAI_CLIENT_ID" ""
$clientSecret = Get-EnvValue $envValues "HYUNDAI_CLIENT_SECRET" ""
if (Test-Placeholder $clientId) {
    throw "HYUNDAI_CLIENT_ID is not set in .env. Fill it from Hyundai Developer Center."
}
if (Test-Placeholder $clientSecret) {
    throw "HYUNDAI_CLIENT_SECRET is not set in .env. Fill it from Hyundai Developer Center."
}

$activePublicUrl = $desiredPublicUrl
if (-not $NoNgrok) {
    $activePublicUrl = Start-NgrokIfNeeded $desiredPublicUrl
    if ($activePublicUrl) {
        Set-DotEnvValue -Path $EnvFile -Key "PUBLIC_BASE_URL" -Value $activePublicUrl
        if (-not $desiredPublicUrl -or $desiredPublicUrl -match "your-ngrok-domain") {
            Write-Warn "Dynamic ngrok URL detected. Hyundai developer center Redirect/Callback URLs must be updated to this URL before real OAuth works."
        }
    }
}

if ($NoNgrok -and ($activePublicUrl -match "your-ngrok-domain" -or [string]::IsNullOrWhiteSpace($activePublicUrl))) {
    Write-Warn "PUBLIC_BASE_URL is not a real ngrok URL. QR/OAuth will not work until .env has the registered public URL."
}

if ($activePublicUrl) {
    Update-AndroidLocalProperties $activePublicUrl
}

if (-not $NoDocker) {
    Write-Step "Starting Docker Compose services"
    $composeArgs = @("compose", "-f", $ComposeFile, "up", "-d")
    if (-not $NoRebuild) {
        $composeArgs += "--build"
    }
    Invoke-Checked -FilePath "docker" -ArgumentList $composeArgs

    Write-Step "Waiting for API services"
    Wait-HttpOk "Backend" "http://localhost:$BackendPort/health"
    Wait-HttpOk "PMS" "http://localhost:8001/openapi.json"
    Wait-HttpOk "Mock PG" "http://localhost:8002/openapi.json"
    Wait-HttpOk "Mock Card" "http://localhost:8003/openapi.json"
}

Write-Step "Local E2E stack summary"
Write-Host "Backend local : http://localhost:$BackendPort"
Write-Host "Backend app   : http://10.0.2.2:$BackendPort"
if ($activePublicUrl) {
    Write-Host "ngrok public  : $activePublicUrl"
    Write-Host "Hyundai Account Redirect URL: $activePublicUrl/auth/redirect"
    Write-Host "Hyundai Data Agreement URL  : $activePublicUrl/auth/data-agreement/redirect"
    Write-Host "Hyundai Data Callback URL   : $activePublicUrl/data/callback"
}
Write-Host ""
Write-Host "Next: open Android Studio or install the debug APK, then run the AAOS app."
