param(
    [switch]$ListFiles
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $ProjectRoot "public-release.json"

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "public-release.json was not found."
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$tracked = git -C $ProjectRoot -c core.quotepath=false ls-files --cached --others --exclude-standard
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read tracked files."
}

function Matches-AnyPattern {
    param([string]$Path, [string[]]$Patterns)
    foreach ($pattern in $Patterns) {
        if ($Path -like $pattern) { return $true }
    }
    return $false
}

$candidate = $tracked |
    ForEach-Object { $_ -replace "\\", "/" } |
    Where-Object { Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf } |
    Where-Object { Matches-AnyPattern -Path $_ -Patterns $manifest.include } |
    Where-Object { -not (Matches-AnyPattern -Path $_ -Patterns $manifest.exclude) } |
    Sort-Object -Unique

$forbidden = $candidate | Where-Object {
    $_ -eq ".env" -or
    $_ -like "docs/*" -or
    $_ -like ".agents/*" -or
    $_ -like ".claude/*" -or
    $_ -like ".secrets/*" -or
    $_ -like "*.local.json" -or
    $_ -like "*.log"
}

if ($forbidden) {
    $joined = $forbidden -join [Environment]::NewLine
    throw "Public release candidate contains forbidden files:$([Environment]::NewLine)$joined"
}

if ($ListFiles) {
    $candidate
}

Write-Host "[Echora] Public release boundary passed: $($candidate.Count) worktree files selected; internal docs and local artifacts excluded." -ForegroundColor Green
