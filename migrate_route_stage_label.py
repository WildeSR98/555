"""
Migration: добавить колонку label в pm_route_config_stage.
Запустить один раз: python migrate_route_stage_label.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.database import engine
from sqlalchemy import text, inspect

def run():
    inspector = inspect(engine)
    cols = [c['name'] for c in inspector.get_columns('pm_route_config_stage')]
    if 'label' in cols:
        print("Column 'label' already exists - skipping.")
        return

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE pm_route_config_stage ADD COLUMN label VARCHAR(100)"))
        conn.commit()
    print("Column 'label' added to pm_route_config_stage - OK")


if __name__ == '__main__':
    run()
