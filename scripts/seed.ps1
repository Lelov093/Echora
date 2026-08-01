# Echora Database Seed Script
# Usage: .\scripts\seed.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "services\agent-api"

# Load .env
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $value = $Matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

Write-Host "[Echora] Seeding database..." -ForegroundColor Green
Set-Location $BackendDir
uv run python -m app.db.seed

Write-Host "[Echora] Seed completed." -ForegroundColor Green
