"""
Подключение к базе данных через SQLAlchemy.
Поддержка SQLite (разработка) и PostgreSQL (продакшн).
Пул соединений: min=1, max=40.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from typing import Optional
from contextlib import contextmanager

from .config import config


def _create_engine():
    """Создание SQLAlchemy engine с учётом типа БД."""
    if config.db.db_type == 'sqlite':
        # SQLite: StaticPool для потокобезопасности
        return create_engine(
            config.db.url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=config.debug,
        )
    else:
        # PostgreSQL: QueuePool с настраиваемым размером
        return create_engine(
            config.db.url,
            poolclass=QueuePool,
            pool_size=config.db.pool_min,
            max_overflow=config.db.pool_max - config.db.pool_min,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=config.db.connect_timeout,
            echo=config.debug,
        )


# Глобальные объекты
engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_session() -> Session:
    """Получить новую сессию БД (для десктопного приложения)."""
    return SessionLocal()


@contextmanager
def session_scope():
    """Контекстный менеджер для работы с сессией БД (с commit/rollback)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """Генератор сессий для FastAPI Depends (автозакрытие после запроса)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> tuple[bool, str]:
    """
    Проверка подключения к БД.
    Returns: (success: bool, message: str)
    """
    try:
        with engine.connect() as conn:
            if config.db.db_type == 'sqlite':
                result = conn.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                return True, f"SQLite {version}"
            else:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                return True, f"PostgreSQL: {version[:30]}..."
    except Exception as e:
        return False, str(e)
