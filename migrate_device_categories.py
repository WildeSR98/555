"""
Миграция: создать таблицу pm_device_category и заполнить из хардкода.
Запуск: python migrate_device_categories.py
"""
import sys
sys.path.insert(0, '.')

from src.database import engine, SessionLocal
from src.models import Base, DeviceCategory, Device

# Создать таблицу если не существует
Base.metadata.create_all(engine, tables=[
    Base.metadata.tables['pm_device_category']
])
print("Таблица pm_device_category создана (или уже существует).")

db = SessionLocal()
try:
    existing = {c.code for c in db.query(DeviceCategory).all()}
    print(f"Уже в БД: {existing}")

    added = 0
    for code, display_name in Device.DEVICE_TYPE_DISPLAY.items():
        if code in existing:
            continue  # Не перезаписываем
        sn_prefix = Device.SN_PREFIXES.get(code, None)
        db.add(DeviceCategory(
            code=code,
            display_name=display_name,
            sn_prefix=sn_prefix,
            sort_order=100,
        ))
        added += 1
        print(f"  + {code}: {display_name} (prefix={sn_prefix})")

    db.commit()
    print(f"\nГотово! Добавлено {added} категорий.")
    total = db.query(DeviceCategory).count()
    print(f"Всего в таблице: {total}")
finally:
    db.close()
