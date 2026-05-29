param(
    [string]$RegistryImage = "",
    [string]$Registry = "",
    [string]$Tag = "",
    [string[]]$Services = @("carpayin-backend", "mock-card", "mock-pg", "pms"),
    [switch]$PushLatest,
    [switch]$NoLatest,
    [string]$RegistryUser = "",
    [string]$RegistryToken = ""
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
    $hostName = ""
    $path = ""

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
        throw "Registry image must include a registry host, for example registry.gitlab.com/group/project."
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

if (-not $Tag) {
    $exactTag = git describe --tags --exact-match 2>$null
    if ($exactTag) {
        $Tag = $exactTag.Trim()
    }
}
if (-not $Tag) {
    throw "Set -Tag with a release tag such as v1 or v2."
}
if ($Tag -notmatch "^v[0-9]+(\.[0-9]+)*$") {
    throw "Tag must look like v1, v2, or v1.1. Received: $Tag"
}

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

foreach ($service in $Services) {
    $image = "$RegistryImage/$service"
    Write-Host "Building $image`:$Tag from SERVICE_NAME=$service"
    docker build `
        --pull `
        -f services/Dockerfile `
        --build-arg "SERVICE_NAME=$service" `
        -t "$image`:$Tag" `
        services

    Write-Host "Pushing $image`:$Tag"
    docker push "$image`:$Tag"

    if (-not $NoLatest) {
        Write-Host "Tagging and pushing $image`:latest"
        docker tag "$image`:$Tag" "$image`:latest"
        docker push "$image`:latest"
    }
}

Write-Host "Done."
Write-Host "Registry image base: $RegistryImage"
Write-Host "Tag: $Tag"
