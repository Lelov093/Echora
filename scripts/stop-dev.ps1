# Echora Development Stop Script
# Usage: .\scripts\stop-dev.ps1

Write-Host "[Echora] Stopping development servers..." -ForegroundColor Yellow

$ProjectRoot = (Split-Path -Parent $PSScriptRoot).ToLowerInvariant()
$targets = Get-CimInstance Win32_Process | Where-Object {
    $commandLine = [string]$_.CommandLine
    $normalized = $commandLine.ToLowerInvariant()
    $belongsToEchora = $normalized.Contains($ProjectRoot)
    $isBackend = $normalized.Contains("uvicorn") -and $normalized.Contains("app.main:app")
    $isFrontend = $normalized.Contains("next dev") -or $normalized.Contains("next start")
    $belongsToEchora -and ($isBackend -or $isFrontend)
}

if (-not $targets) {
    Write-Host "[Echora] No Echora development processes found." -ForegroundColor Yellow
    exit 0
}

foreach ($target in $targets) {
    Write-Host "[Echora] Stopping PID $($target.ProcessId): $($target.Name)" -ForegroundColor Yellow
    Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "[Echora] Development servers stopped." -ForegroundColor Green
