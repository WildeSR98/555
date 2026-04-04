#!/usr/bin/env python3
"""
Скрипт миграции данных из SQLite в PostgreSQL для Production Manager.

Использование:
    python migrate_sqlite_to_pg.py

Требования:
    - Файл .env с настройками для целевой базы PostgreSQL (DB_TYPE=postgresql)
    - Установленный пакет psycopg2-binary
    - Исходная база данных SQLite должна существовать (по умолчанию production.db)
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, MetaData, Table
from sqlalchemy.orm import sessionmaker
import psycopg2
from psycopg2 import sql

# Загрузка переменных окружения
load_dotenv()

def get_config():
    """Получение конфигурации из переменных окружения."""
    return {
        'sqlite_path': os.getenv('SQLITE_PATH', 'production.db'),
        'pg_host': os.getenv('DB_HOST', 'localhost'),
        'pg_port': os.getenv('DB_PORT', '5432'),
        'pg_db': os.getenv('DB_NAME', 'production_db'),
        'pg_user': os.getenv('DB_USER', 'prod_user'),
        'pg_password': os.getenv('DB_PASSWORD', ''),
    }

def get_sqlite_engine(sqlite_path):
    """Создание движка для SQLite."""
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"База данных SQLite не найдена: {sqlite_path}")
    return create_engine(f'sqlite:///{sqlite_path}')

def get_pg_connection(config):
    """Создание подключения к PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=config['pg_host'],
            port=config['pg_port'],
            dbname=config['pg_db'],
            user=config['pg_user'],
            password=config['pg_password']
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        raise ConnectionError(f"Не удалось подключиться к PostgreSQL: {e}")

def migrate_data():
    """Основная функция миграции."""
    config = get_config()
    
    print(f"🔍 Проверка исходной базы SQLite: {config['sqlite_path']}...")
    try:
        sqlite_engine = get_sqlite_engine(config['sqlite_path'])
        sqlite_inspector = inspect(sqlite_engine)
        table_names = sqlite_inspector.get_table_names()
        # Исключаем служебные таблицы SQLite
        table_names = [t for t in table_names if not t.startswith('sqlite_')]
        print(f"✅ Найдено таблиц: {len(table_names)}")
    except Exception as e:
        print(f"❌ Ошибка чтения SQLite: {e}")
        return

    print(f"🔍 Подключение к PostgreSQL ({config['pg_host']}/{config['pg_db']})...")
    try:
        pg_conn = get_pg_connection(config)
        pg_cursor = pg_conn.cursor()
        print("✅ Подключение успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения к PostgreSQL: {e}")
        return

    print("🚀 Начало миграции...\n")
    
    total_rows = 0
    
    for table_name in table_names:
        print(f"📦 Миграция таблицы: {table_name}...")
        
        try:
            # Чтение данных из SQLite
            sqlite_metadata = MetaData()
            sqlite_table = Table(table_name, sqlite_metadata, autoload_with=sqlite_engine)
            
            with sqlite_engine.connect() as conn:
                result = conn.execute(sqlite_table.select())
                rows = result.fetchall()
                columns = [col.name for col in sqlite_table.columns]
            
            if not rows:
                print(f"   ⚪ Таблица пуста, пропуск.")
                continue

            # Подготовка SQL для вставки в PostgreSQL
            # Используем экранирование имен для безопасности
            safe_columns = [sql.Identifier(col) for col in columns]
            placeholders = [sql.Literal("%s") for _ in columns]
            
            insert_query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({values})").format(
                table=sql.Identifier(table_name),
                fields=sql.SQL(', ').join(safe_columns),
                values=sql.SQL(', ').join(placeholders)
            )
            
            # Вставка данных
            inserted_count = 0
            for row in rows:
                try:
                    # Обработка специфичных типов данных при необходимости
                    clean_row = []
                    for val in row:
                        if isinstance(val, bytes):
                            # Для blob данных в PostgreSQL используем bytearray
                            clean_row.append(memoryview(val))
                        else:
                            clean_row.append(val)
                    
                    pg_cursor.execute(insert_query, clean_row)
                    inserted_count += 1
                except Exception as e:
                    print(f"   ⚠️ Ошибка вставки строки: {e}")
                    continue
            
            total_rows += inserted_count
            print(f"   ✅ Перенесено строк: {inserted_count}/{len(rows)}")
            
        except Exception as e:
            print(f"   ❌ Ошибка обработки таблицы {table_name}: {e}")
            continue

    # Фиксация транзакции
    try:
        pg_conn.commit()
        print(f"\n🎉 Миграция завершена успешно!")
        print(f"📊 Всего перенесено записей: {total_rows}")
    except Exception as e:
        pg_conn.rollback()
        print(f"\n❌ Ошибка при фиксация транзакции: {e}")
        print("Откат изменений выполнен.")
    finally:
        pg_cursor.close()
        pg_conn.close()

if __name__ == "__main__":
    try:
        migrate_data()
    except KeyboardInterrupt:
        print("\n⛔ Миграция прервана пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)
