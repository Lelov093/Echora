# Echora Environment Check Script
# Usage: .\scripts\check-env.ps1

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Echora Environment Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allOk = $true

# Check Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[OK] Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[MISSING] Node.js not found" -ForegroundColor Red
    $allOk = $false
}

# Check npm
try {
    $npmVersion = npm --version 2>&1
    Write-Host "[OK] npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "[MISSING] npm not found" -ForegroundColor Red
    $allOk = $false
}

# Check uv
try {
    $uvVersion = uv --version 2>&1
    Write-Host "[OK] uv: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "[MISSING] uv not found" -ForegroundColor Red
    $allOk = $false
}

# Check Python
try {
    $BackendDir = Join-Path $ProjectRoot "services\agent-api"
    Push-Location $BackendDir
    $pyVersion = uv run python --version 2>&1
    Pop-Location
    Write-Host "[OK] Python (via uv): $pyVersion" -ForegroundColor Green
} catch {
    if ((Get-Location).Path -ne $ProjectRoot) {
        Pop-Location -ErrorAction SilentlyContinue
    }
    Write-Host "[WARN] Python not available via uv in project" -ForegroundColor Yellow
}

# Check .env
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Write-Host "[OK] .env found" -ForegroundColor Green
} else {
    Write-Host "[WARN] .env not found. Copy .env.example to .env" -ForegroundColor Yellow
}

# Check project directories
$dirs = @(
    "apps/web",
    "services/agent-api",
    "packages/shared-types",
    "docs",
    "scripts",
    ".cache",
    ".data",
    ".logs",
    ".sandbox"
)
foreach ($dir in $dirs) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (Test-Path $fullPath) {
        Write-Host "[OK] Directory exists: $dir" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Directory not found: $dir" -ForegroundColor Yellow
    }
}

Write-Host ""
if ($allOk) {
    Write-Host "[Echora] Environment check passed." -ForegroundColor Green
} else {
    Write-Host "[Echora] Some checks failed. Please fix before running." -ForegroundColor Red
}
