param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [switch]$InitializeGit,

    [string]$AuthorName = "Lelov",

    [string]$AuthorEmail = "311008182+Lelov093@users.noreply.github.com",

    [string]$CommitMessage = "chore: publish initial Echora release"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$DestinationPath = [IO.Path]::GetFullPath($Destination)

if (-not [IO.Path]::IsPathRooted($Destination)) {
    throw "Destination must be an absolute path."
}

$projectPrefix = $ProjectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$destinationPrefix = $DestinationPath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (
    $DestinationPath -eq $ProjectRoot -or
    $ProjectRoot.StartsWith($destinationPrefix, [StringComparison]::OrdinalIgnoreCase)
) {
    throw "Destination must not be the project root or one of its parent directories."
}

if (Test-Path -LiteralPath $DestinationPath) {
    $existing = @(Get-ChildItem -LiteralPath $DestinationPath -Force)
    if ($existing.Count -gt 0) {
        throw "Destination already exists and is not empty: $DestinationPath"
    }
} else {
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
}

$boundaryCheck = Join-Path $PSScriptRoot "check-public-release.ps1"
$languageCheck = Join-Path $PSScriptRoot "check-public-language.ps1"

& $boundaryCheck
& $languageCheck

$candidate = @(& $boundaryCheck -ListFiles)
if ($candidate.Count -eq 0) {
    throw "The public release allowlist selected no files."
}

foreach ($relativePath in $candidate) {
    $sourcePath = Join-Path $ProjectRoot $relativePath
    $targetPath = Join-Path $DestinationPath $relativePath
    $targetParent = Split-Path -Parent $targetPath
    if (-not (Test-Path -LiteralPath $targetParent)) {
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $sourcePath -Destination $targetPath
}

$sourceHashes = @{}
foreach ($relativePath in $candidate) {
    $sourceHashes[$relativePath] = (Get-FileHash -LiteralPath (Join-Path $ProjectRoot $relativePath) -Algorithm SHA256).Hash
}

$exported = @(
    Get-ChildItem -LiteralPath $DestinationPath -File -Recurse -Force |
        ForEach-Object {
            $_.FullName.Substring($DestinationPath.TrimEnd("\").Length + 1).Replace("\", "/")
        } |
        Sort-Object -Unique
)

$expected = @($candidate | Sort-Object -Unique)
$pathDifference = @(Compare-Object -ReferenceObject $expected -DifferenceObject $exported)
if ($pathDifference.Count -gt 0) {
    throw "Exported file set differs from the allowlist."
}

foreach ($relativePath in $expected) {
    $targetHash = (Get-FileHash -LiteralPath (Join-Path $DestinationPath $relativePath) -Algorithm SHA256).Hash
    if ($targetHash -ne $sourceHashes[$relativePath]) {
        throw "Exported file hash differs from source: $relativePath"
    }
}

if ($InitializeGit) {
    git -C $DestinationPath init --initial-branch=main | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unable to initialize the public repository." }

    git -C $DestinationPath config user.name $AuthorName
    git -C $DestinationPath config user.email $AuthorEmail
    git -C $DestinationPath config core.autocrlf false
    git -C $DestinationPath add --all
    if ($LASTEXITCODE -ne 0) { throw "Unable to stage the public candidate." }

    git -C $DestinationPath commit -m $CommitMessage | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the initial public commit." }

    $commitCount = git -C $DestinationPath rev-list --count HEAD
    if ($LASTEXITCODE -ne 0 -or $commitCount -ne "1") {
        throw "The public repository must contain exactly one commit."
    }
}

Write-Host (
    "[Echora] Public release candidate built at {0}: {1} files{2}." -f
    $DestinationPath,
    $expected.Count,
    $(if ($InitializeGit) { ", one initial Git commit" } else { "" })
) -ForegroundColor Green
