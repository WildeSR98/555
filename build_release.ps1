# Сборка Production Manager в .exe
# Запуск: .\build_release.ps1

Write-Host "Сборка Production Manager..." -ForegroundColor Cyan

# Сборка
.venv\Scripts\pyinstaller.exe production_manager.spec --clean --noconfirm

if ($LASTEXITCODE -eq 0) {
    # Копируем актуальную базу данных
    Copy-Item -Path "db.sqlite3" -Destination "dist\ProductionManager\db.sqlite3" -Force
    Write-Host "База данных скопирована." -ForegroundColor Green
    Write-Host "Готово! Сборка: dist\ProductionManager\ProductionManager.exe" -ForegroundColor Green
} else {
    Write-Host "Ошибка сборки!" -ForegroundColor Red
}
