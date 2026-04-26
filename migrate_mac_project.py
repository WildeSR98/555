"""
Миграция: добавить поле project_id в таблицу pm_mac_address.
Привязка MAC к проекту вместо устройства.

Запуск: python migrate_mac_project.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        # Проверить, есть ли уже колонка
        try:
            conn.execute(text("SELECT project_id FROM pm_mac_address LIMIT 1"))
            print("[OK] Колонка project_id уже существует — миграция не нужна.")
            return
        except Exception:
            pass

        # Добавляем колонку
        print("[MIGRATE] Добавляем колонку project_id в pm_mac_address...")
        try:
            conn.execute(text(
                "ALTER TABLE pm_mac_address ADD COLUMN project_id INTEGER REFERENCES tasks_project(id) ON DELETE SET NULL"
            ))
            conn.commit()
            print("[OK] Колонка project_id добавлена успешно.")
        except Exception as e:
            print(f"[ERROR] {e}")
            # Для SQLite — fallback
            try:
                conn.rollback()
                conn.execute(text(
                    "ALTER TABLE pm_mac_address ADD COLUMN project_id INTEGER"
                ))
                conn.commit()
                print("[OK] Колонка project_id добавлена (SQLite fallback).")
            except Exception as e2:
                print(f"[ERROR] Не удалось добавить колонку: {e2}")

        # Заполнить project_id из device_id для существующих записей
        print("[MIGRATE] Заполняем project_id из связанных устройств...")
        try:
            conn.execute(text("""
                UPDATE pm_mac_address
                SET project_id = (
                    SELECT d.project_id
                    FROM tasks_device d
                    WHERE d.id = pm_mac_address.device_id
                )
                WHERE device_id IS NOT NULL AND project_id IS NULL
            """))
            conn.commit()
            updated = conn.execute(text(
                "SELECT COUNT(*) FROM pm_mac_address WHERE project_id IS NOT NULL"
            )).scalar()
            print(f"[OK] Обновлено записей с project_id: {updated}")
        except Exception as e:
            print(f"[WARN] Ошибка при заполнении project_id: {e}")


if __name__ == '__main__':
    migrate()
