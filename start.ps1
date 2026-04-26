# Запуск веб-сервера Production Manager
# Использует .venv автоматически, без ручной активации

$VenvPython = "$PSScriptRoot\.venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: .venv не найден. Создайте его: python -m venv .venv" -ForegroundColor Red
    Write-Host "Затем: .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting Production Manager..." -ForegroundColor Green
Write-Host "URL: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

$env:PYTHONPATH = $PSScriptRoot
& $VenvPython -m uvicorn web.main:app --host 127.0.0.1 --port 8000 --reload
