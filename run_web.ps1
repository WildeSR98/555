# Production Manager — Web Server
param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$env:PYTHONPATH = "$PSScriptRoot"

$ReloadArg = if ($Reload) { "--reload" } else { "" }

Write-Host "Starting Production Manager Web Server..." -ForegroundColor Green
Write-Host "URL: http://$Host`:$Port" -ForegroundColor Cyan
Write-Host "API Docs: http://$Host`:$Port/docs" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn web.main:app --host $Host --port $Port $ReloadArg
