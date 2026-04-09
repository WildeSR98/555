"""
Быстрая миграция данных из SQLite в PostgreSQL.
Копирует все таблицы из db.sqlite3 в PostgreSQL (docker-compose).

Использование: python web/setup_db.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text, inspect
from src.models import Base
from src.config import config


def setup_postgres():
    """Создать все таблицы в PostgreSQL."""
    if config.db.db_type != 'postgresql':
        print("❌ DB_TYPE должен быть 'postgresql'")
        print(f"Текущий: {config.db.db_type}")
        return False
    
    print(f"🔌 Подключение к PostgreSQL: {config.db.host}:{config.db.port}/{config.db.name}")
    
    try:
        # Создаём engine
        engine = create_engine(config.db.url)
        
        # Создаём все таблицы
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы/проверены")
        
        # Проверяем соединение
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ PostgreSQL: {version[:40]}...")
        
        # Список таблиц
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"📊 Таблиц в БД: {len(tables)}")
        for table in sorted(tables):
            print(f"   - {table}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def migrate_from_sqlite():
    """Миграция данных из SQLite в PostgreSQL."""
    sqlite_path = Path(__file__).resolve().parent.parent / "db.sqlite3"
    if not sqlite_path.exists():
        print("❌ SQLite файл не найден:", sqlite_path)
        return False
    
    print(f"📂 SQLite: {sqlite_path}")
    
    try:
        # Подключаемся к SQLite
        sqlite_url = f"sqlite:///{sqlite_path}"
        sqlite_engine = create_engine(sqlite_url)
        
        # Подключаемся к PostgreSQL
        pg_engine = create_engine(config.db.url)
        
        # Получаем список таблиц из SQLite
        inspector = inspect(sqlite_engine)
        tables = [t for t in inspector.get_table_names() if not t.startswith('sqlite_')]
        
        print(f"📋 Таблиц для миграции: {len(tables)}")
        
        migrated = 0
        for table in tables:
            # Читаем данные из SQLite
            with sqlite_engine.connect() as src_conn:
                result = src_conn.execute(text(f"SELECT * FROM {table}"))
                rows = result.fetchall()
                columns = result.keys()
                
                if not rows:
                    print(f"   ⏭ {table}: пусто")
                    continue
                
                # Вставляем в PostgreSQL
                with pg_engine.begin() as dst_conn:
                    # Очищаем таблицу
                    dst_conn.execute(text(f"DELETE FROM {table}"))
                    
                    # Вставляем данные
                    for row in rows:
                        placeholders = ", ".join([f":{col}" for col in columns])
                        columns_str = ", ".join(columns)
                        insert_sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                        
                        try:
                            dst_conn.execute(text(insert_sql), dict(zip(columns, row)))
                        except Exception as e:
                            print(f"   ⚠ {table}: ошибка вставки — {e}")
                            continue
                
                print(f"   ✅ {table}: {len(rows)} записей")
                migrated += 1
        
        print(f"\n✅ Миграция завершена: {migrated}/{len(tables)} таблиц")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Production Manager — Database Setup & Migration")
    print("=" * 60)
    print()
    
    # 1. Создаём таблицы в PostgreSQL
    if setup_postgres():
        print()
        # 2. Мигрируем данные
        migrate_from_sqlite()
    else:
        print("\n⚠ Настройте .env для подключения к PostgreSQL")
