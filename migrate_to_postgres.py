"""
Скрипт миграции данных из SQLite в PostgreSQL.
Использует модели из src/models.py для создания схемы и переноса данных.

Использование:
    python migrate_to_postgres.py
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# Добавляем src в путь импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Импортируем модели и конфиг
from models import Base, User, Project, Device, Operation, SerialNumber, ScanLog, ProductionStep
# from config import settings # Если бы мы использовали конфиг напрямую, но тут зададим вручную для миграции

def get_sqlite_session(db_path='production.db'):
    """Подключение к локальной SQLite базе."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"База данных {db_path} не найдена.")
    
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session(), engine

def get_postgres_session(host, port, dbname, user, password):
    """Подключение к целевой PostgreSQL базе."""
    conn_str = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'
    engine = create_engine(conn_str)
    
    # Создаем таблицы, если их нет (Base.metadata.create_all работает для любого диалекта)
    print("Создание схемы таблиц в PostgreSQL...")
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return Session(), engine

def migrate_data():
    print("--- Начало миграции SQLite -> PostgreSQL ---")
    
    # 1. Настройки целевой БД (можно вынести в .env или ввести вручную)
    # Для безопасности лучше запросить ввод или взять из временных переменных
    pg_config = {
        'host': input("Host PostgreSQL (например, 192.168.1.50): ") or 'localhost',
        'port': input("Port (по умолчанию 5432): ") or '5432',
        'dbname': input("Имя БД (например, production_manager): ") or 'production_manager',
        'user': input("Пользователь: ") or 'pm_user',
        'password': input("Пароль: ") # Скрытый ввод лучше делать через getpass, но оставим просто для скрипта
    }

    try:
        sqlite_session, sqlite_engine = get_sqlite_session()
        pg_session, pg_engine = get_postgres_session(**pg_config)
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return

    # Список моделей для переноса в правильном порядке (из-за внешних ключей)
    # Порядок важен: сначала справочники, потом зависимые таблицы
    models_order = [
        User,           # Пользователи (не зависят от других)
        Project,        # Проекты
        Device,         # Устройства (зависят от Project)
        ProductionStep, # Этапы конвейера
        Operation,      # Операции (зависят от Device/Step)
        SerialNumber,   # Серийные номера (зависят от Device)
        ScanLog         # Логи сканирования (зависят от SN/User)
    ]

    total_migrated = 0

    for model in models_order:
        table_name = model.__tablename__
        print(f"🔄 Перенос таблицы: {table_name}...")
        
        # Получаем все данные из SQLite
        source_data = sqlite_session.query(model).all()
        
        if not source_data:
            print(f"   ⚪ Таблица пуста.")
            continue
        
        # Очищаем целевую таблицу перед вставкой (на случай повторного запуска)
        pg_session.query(model).delete()
        pg_session.commit()
        
        count = 0
        for item in source_data:
            # Detach объект от сессии SQLite, чтобы можно было добавить в новую сессию
            pg_session.expunge(item)
            
            # Сбрасываем состояние объекта, чтобы SQLAlchemy считал его новым
            # Важно: для сложных связей может потребоваться ручное копирование атрибутов,
            # но для простых случаев expunge + add работает, если ID генерируются БД.
            # Однако, чтобы сохранить старые ID (важно для связей), нужно явно указать их.
            
            # Создаем новый экземпляр с теми же данными
            # Получаем колонки модели
            columns = [c.key for c in model.__table__.columns]
            data_dict = {col: getattr(item, col) for col in columns}
            
            new_item = model(**data_dict)
            pg_session.add(new_item)
            count += 1
            
        pg_session.commit()
        print(f"   ✅ Перенесено записей: {count}")
        total_migrated += count

    sqlite_session.close()
    pg_session.close()
    
    print(f"\n🎉 Миграция завершена! Всего перенесено: {total_migrated} записей.")
    print("Не забудьте обновить файл .env для переключения приложения на новую БД.")

if __name__ == "__main__":
    # Проверка наличия драйвера
    try:
        import psycopg2
    except ImportError:
        print("❌ Ошибка: Модуль psycopg2 не найден. Выполните: pip install psycopg2-binary")
        sys.exit(1)

    migrate_data()
