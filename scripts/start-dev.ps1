# Echora Development Start Script
# Usage: .\scripts\start-dev.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

# ── Local Cache Configuration ───────────────────────────────────────
$env:UV_CACHE_DIR = Join-Path $ProjectRoot ".cache\uv"
$env:PIP_CACHE_DIR = Join-Path $ProjectRoot ".cache\pip"
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot ".cache\pycache"
$env:NPM_CONFIG_CACHE = Join-Path $ProjectRoot ".cache\npm"
$env:DOTENV_PATH = Join-Path $ProjectRoot ".env"

# ── Load .env if exists ─────────────────────────────────────────────
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Write-Host "[Echora] Loading .env from $envFile" -ForegroundColor Cyan
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $value = $Matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
} else {
    Write-Host "[Echora] Warning: .env not found. Copy .env.example to .env and configure." -ForegroundColor Yellow
}

# ── Create runtime directories ──────────────────────────────────────
@(".cache", ".data", ".logs", ".sandbox") | ForEach-Object {
    $dir = Join-Path $ProjectRoot $_
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Echora Development Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Start Backend ───────────────────────────────────────────────────
Write-Host "[Echora] Starting Backend (agent-api)..." -ForegroundColor Green
$backendDir = Join-Path $ProjectRoot "services\agent-api"
# Use uvicorn directly to avoid Windows GBK encoding issue with fastapi CLI
# Set PYTHONUTF8 to handle emoji in console output
Start-Process -FilePath "uv" -ArgumentList "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010", "--reload" -WorkingDirectory $backendDir -WindowStyle Hidden

# ── Start Frontend ──────────────────────────────────────────────────
Write-Host "[Echora] Starting Frontend (apps/web)..." -ForegroundColor Green
$frontendDir = Join-Path $ProjectRoot "apps\web"
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $frontendDir -WindowStyle Hidden

Write-Host ""
Write-Host "[Echora] Both servers starting..." -ForegroundColor Cyan
Write-Host "  Backend  : http://127.0.0.1:8010" -ForegroundColor White
Write-Host "  Frontend : http://localhost:3000" -ForegroundColor White
Write-Host "  API Docs : http://127.0.0.1:8010/docs" -ForegroundColor White
Write-Host ""
Write-Host "[Echora] Run .\scripts\stop-dev.ps1 to stop servers." -ForegroundColor Yellow
