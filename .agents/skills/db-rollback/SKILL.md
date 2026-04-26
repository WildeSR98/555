---
name: db-rollback
description: Rules and tools for database backup and rollback when making schema or data changes.
---

# Database Rollback Skill

This rule is MANDATORY before any database schema change (Alembic migrations, column deletion, data type changes) or bulk business data modifications.

## Core Rules

1. **Backup before changes**: Before running `alembic upgrade`, `alembic downgrade`, or migration scripts (e.g., `migrate_to_postgres.py`), create a backup of the current DB.
2. **DB type**: Tools support automatic DB type detection (SQLite or PostgreSQL) via `.env` file.
3. **Storage**: Backups are saved to `backups/` directory in project root with a timestamp in the filename.

## Using the Tool

For automatic backup creation, use the script:

```bash
python .agents/skills/db-rollback/scripts/backup.py
```

### Manual Backup

**For SQLite:**
```bash
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d_%H%M%S).bak
```

**For PostgreSQL:**
```bash
pg_dump -h localhost -U pm_user -F c -f backups/production_db.$(date +%Y%m%d_%H%M%S).sql production_db
```

## Rollback Process

If critical errors occur after changes:

1. Stop the application (Desktop and Web).
2. Remove the corrupted DB file (for SQLite) or clear the schema (for PostgreSQL).
3. Restore from the latest backup:

**For SQLite:**
```bash
cp backups/db.sqlite3.TIMESTAMP.bak db.sqlite3
```

**For PostgreSQL:**
```bash
pg_restore -h localhost -U pm_user -d production_db backups/production_db.TIMESTAMP.sql
```

4. Start the application and verify data integrity.
