param(
    [string]$RegistryImage = "",
    [string]$Registry = "",
    [string]$Tag = "latest",
    [string]$RegistryUser = "",
    [string]$RegistryToken = "",
    [switch]$SkipLogin
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $root = git rev-parse --show-toplevel 2>$null
    if (-not $root) {
        throw "Run this script inside the git repository."
    }
    return $root.Trim()
}

function Get-GitLabRegistryImageFromOrigin {
    $remote = git remote get-url origin 2>$null
    if (-not $remote) {
        return ""
    }

    $remote = $remote.Trim()
    if ($remote -match "^https?://([^/]+)/(.+)$") {
        $hostName = $Matches[1]
        $path = $Matches[2]
    }
    elseif ($remote -match "^git@([^:]+):(.+)$") {
        $hostName = $Matches[1]
        $path = $Matches[2]
    }
    else {
        return ""
    }

    $path = $path -replace "\.git$", ""
    if ($hostName -eq "gitlab.com") {
        return "registry.gitlab.com/$path"
    }
    return "registry.$hostName/$path"
}

function Get-RegistryHost([string]$image) {
    if ($image -notmatch "^([^/]+)/") {
        throw "Registry image must include a registry host."
    }
    return $Matches[1]
}

function ConvertTo-PlainText([securestring]$secure) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$root = Get-RepoRoot
Set-Location $root

if (-not $RegistryImage) {
    $RegistryImage = $env:CI_REGISTRY_IMAGE
}
if (-not $RegistryImage) {
    $RegistryImage = Get-GitLabRegistryImageFromOrigin
}
if (-not $RegistryImage) {
    throw "Set -RegistryImage, for example registry.gitlab.com/group/project."
}
$RegistryImage = $RegistryImage.TrimEnd("/")

if (-not $Registry) {
    $Registry = $env:CI_REGISTRY
}
if (-not $Registry) {
    $Registry = Get-RegistryHost $RegistryImage
}

if (-not $Tag -or $Tag.Trim() -eq "") {
    $Tag = "latest"
}

if (-not $SkipLogin) {
    if (-not $RegistryUser) {
        $RegistryUser = $env:CI_REGISTRY_USER
    }
    if (-not $RegistryUser) {
        $RegistryUser = $env:GITLAB_REGISTRY_USER
    }
    if (-not $RegistryUser) {
        $RegistryUser = Read-Host "GitLab registry username"
    }

    if (-not $RegistryToken) {
        $RegistryToken = $env:CI_REGISTRY_PASSWORD
    }
    if (-not $RegistryToken) {
        $RegistryToken = $env:GITLAB_REGISTRY_TOKEN
    }
    if (-not $RegistryToken) {
        $secureToken = Read-Host "GitLab registry token/password" -AsSecureString
        $RegistryToken = ConvertTo-PlainText $secureToken
    }

    Write-Host "Logging in to $Registry as $RegistryUser"
    $RegistryToken | docker login $Registry -u $RegistryUser --password-stdin
}

$env:CI_REGISTRY_IMAGE = $RegistryImage
$env:IMAGE_TAG = $Tag

Write-Host "Deploying images from $RegistryImage with tag $Tag"
docker compose -f docker-compose.yaml -f docker-compose.registry.yaml pull carpayin-backend mock-card mock-pg pms
docker compose -f docker-compose.yaml -f docker-compose.registry.yaml up -d --no-build
docker compose -f docker-compose.yaml -f docker-compose.registry.yaml ps
