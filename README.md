# Production Manager 🏭

Windows-приложение для управления производственным конвейером.
Десктопный клиент (PyQt6) для системы office-task-manager.

## Возможности

- **Дашборд** — обзор рабочих мест, активных сессий, сводные показатели
- **Проекты** — дерево: Проект → Устройства → Операции
- **Конвейер** — визуальный обзор всех этапов производства
- **Сканирование** — рабочий процесс: QR работника → SN устройства → Действие
- **Статус SN** — поиск устройства по серийному номеру с историей
- **Аналитика** — графики производственных показателей

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python src/main.py
```

## Настройка БД

Скопируйте `.env.example` в `.env` и настройте:

```ini
# SQLite (разработка)
DB_TYPE=sqlite
DB_PATH=db.sqlite3

# PostgreSQL (продакшн)
DB_TYPE=postgresql
DB_HOST=your-server.com
DB_PORT=5432
DB_NAME=production_db
DB_USER=app_user
DB_PASSWORD=your_password
```

## Сборка .exe

```bash
python build.py
```

Результат: `dist/ProductionManager.exe`

## Технологии

- **GUI**: PyQt6
- **ORM**: SQLAlchemy
- **БД**: SQLite / PostgreSQL
- **Графики**: matplotlib
- **Сборка**: PyInstaller
