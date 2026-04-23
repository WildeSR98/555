"""
Migration: создать таблицу pm_mac_address (пул MAC-адресов).
Запустить один раз: python migrate_mac_pool.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.database import engine
from sqlalchemy import text, inspect


def run():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'pm_mac_address' in tables:
        print("Table 'pm_mac_address' already exists — skipping.")
        return

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE pm_mac_address (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                mac        VARCHAR(17) NOT NULL UNIQUE,
                mac_type   VARCHAR(10) NOT NULL,
                is_used    BOOLEAN     NOT NULL DEFAULT 0,
                device_id  INTEGER     REFERENCES tasks_device(id) ON DELETE SET NULL,
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX ix_pm_mac_address_mac ON pm_mac_address (mac)"))
        conn.commit()

    print("Table 'pm_mac_address' created — OK")


if __name__ == '__main__':
    run()
