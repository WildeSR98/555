---
name: db-rollback
description: Правила и инструменты для резервного копирования и отката БД при внесении изменений.
---

# Database Rollback Skill

Это правило ОБЯЗАТЕЛЬНО к выполнению перед любым изменением структуры базы данных (миграции Alembic, удаление колонок, изменение типов данных) или массовым изменением бизнес-данных.

## Основные правила

1. **Бэкап перед изменениями**: Перед выполнением `alembic upgrade`, `alembic downgrade` или запуском скриптов миграции (например, `migrate_to_postgres.py`), необходимо создать резервную копию текущей БД.
2. **Тип БД**: Инструменты поддерживают автоматическое определение типа БД (SQLite или PostgreSQL) через файл `.env`.
3. **Хранение**: Бэкапы сохраняются в директорию `backups/` в корне проекта с временной меткой в названии.

## Использование инструмента

Для автоматического создания бэкапа используйте скрипт:

```bash
python .agents/skills/db-rollback/scripts/backup.py
```

### Ручное резервное копирование

**Для SQLite:**
```bash
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d_%H%M%S).bak
```

**Для PostgreSQL:**
```bash
pg_dump -h localhost -U pm_user -F c -f backups/production_db.$(date +%Y%m%d_%H%M%S).sql production_db
```

## Процесс отката (Rollback)

Если после изменений возникли критические ошибки:

1. Остановка приложения (Desktop и Web).
2. Удаление поврежденного файла БД (для SQLite) или очистка схемы (для PostgreSQL).
3. Восстановление из последнего бэкапа:

**Для SQLite:**
```bash
cp backups/db.sqlite3.TIMESTAMP.bak db.sqlite3
```

**Для PostgreSQL:**
```bash
pg_restore -h localhost -U pm_user -d production_db backups/production_db.TIMESTAMP.sql
```

4. Запуск приложения и проверка целостности данных.
