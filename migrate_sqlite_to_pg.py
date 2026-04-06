import sys
import os
from sqlalchemy import create_engine, MetaData, Table, insert, select
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Добавляем текущую директорию в путь для импорта моделей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models import Base
from src.config import config

def migrate():
    # Настройки подключений
    # 1. SQLite (Source)
    sqlite_url = f"sqlite:///{os.path.join(os.getcwd(), 'db.sqlite3')}"
    print(f"🔍 Источник (SQLite): {sqlite_url}")
    engine_sqlite = create_engine(sqlite_url)
    
    # 2. PostgreSQL (Target)
    # Форсируем тип postgresql для миграции
    config.db.db_type = 'postgresql'
    # Убираем sslmode=require для локального докера, если нужно, 
    # но в config.py он зашит. Если в докере нет SSL, может упасть.
    # Для миграции создадим URL вручную без SSL
    pg_url = (
        f"postgresql+psycopg2://{config.db.db_user}:{config.db.db_password}"
        f"@{config.db.db_host}:{config.db.db_port}/{config.db.db_name}"
    )
    print(f"🚀 Цель (PostgreSQL): {pg_url}")
    engine_pg = create_engine(pg_url)

    # Создаем таблицы в PostgreSQL
    print("🛠 Создание таблиц в PostgreSQL...")
    Base.metadata.create_all(engine_pg)
    print("✅ Таблицы созданы.")

    # Метаданные для чтения из SQLite
    metadata_source = MetaData()
    metadata_source.reflect(bind=engine_sqlite)

    # Порядок таблиц для миграции (сначала независимые)
    # Django таблицы сначала, потом приложения
    tables_to_migrate = [
        'auth_group',
        'accounts_user',
        'accounts_user_groups',
        'tasks_project',
        'tasks_devicemodel',
        'tasks_device',
        'tasks_serialnumber',
        'tasks_operation',
        'production_workplace',
        'production_workplace_allowed_groups',
        'production_workplace_allowed_sources',
        'production_worksession',
        'production_worklog',
    ]

    for table_name in tables_to_migrate:
        if table_name not in metadata_source.tables:
            print(f"⚠️ Таблица {table_name} не найдена в SQLite. Пропуск.")
            continue

        print(f"📦 Перенос данных из {table_name}...")
        source_table = metadata_source.tables[table_name]
        target_table = Table(table_name, Base.metadata, autoload_with=engine_pg)

        with engine_sqlite.connect() as conn_src:
            rows = conn_src.execute(select(source_table)).fetchall()
            if not rows:
                print(f"   — Таблица пуста.")
                continue

            # Преобразуем Row в dict
            data = [dict(row._mapping) for row in rows]

            with engine_pg.connect() as conn_target:
                # В PostgreSQL нужно сбросить последовательности ID после вставки 
                # (SQLAlchemy сделает это при вставке с явными ID, но иногда нужно вручную)
                conn_target.execute(insert(target_table), data)
                conn_target.commit()
                print(f"   ✅ Перенесено строк: {len(data)}")

    print("\n🎉 Миграция успешно завершена!")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
