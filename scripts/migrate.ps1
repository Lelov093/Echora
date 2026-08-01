# Echora Database Migration Script
# Usage: .\scripts\migrate.ps1 [upgrade|downgrade|revision]

param(
    [string]$Action = "upgrade"
)

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

Set-Location $BackendDir

switch ($Action) {
    "upgrade" {
        Write-Host "[Echora] Running alembic upgrade head..." -ForegroundColor Green
        uv run alembic upgrade head
    }
    "downgrade" {
        Write-Host "[Echora] Running alembic downgrade -1..." -ForegroundColor Yellow
        uv run alembic downgrade -1
    }
    "revision" {
        $msg = Read-Host "Migration message"
        Write-Host "[Echora] Creating new migration: $msg" -ForegroundColor Green
        uv run alembic revision --autogenerate -m $msg
    }
    default {
        Write-Host "[Echora] Unknown action: $Action. Use upgrade, downgrade, or revision." -ForegroundColor Red
    }
}
