"""
Конфигурация приложения Production Manager.
Чтение настроек из .env файла.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


# Корневая директория проекта
# При сборке PyInstaller: папка, где лежит .exe
# При разработке: корень проекта (на уровень выше src/)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Загрузка .env
load_dotenv(BASE_DIR / '.env')


@dataclass
class DatabaseConfig:
    """Настройки подключения к базе данных."""
    db_type: str = 'sqlite'
    db_path: str = 'db.sqlite3'
    db_host: str = 'localhost'
    db_port: int = 5432
    db_name: str = 'production_db'
    db_user: str = 'prod_user'
    db_password: str = 'strong_password_here'
    pool_min: int = 1
    pool_max: int = 40
    connect_timeout: int = 30

    @property
    def url(self) -> str:
        """Формирование строки подключения SQLAlchemy."""
        if self.db_type == 'sqlite':
            db_path = BASE_DIR / self.db_path
            return f"sqlite:///{db_path}"
        elif self.db_type == 'postgresql':
            return (
                f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
                f"?sslmode=require&connect_timeout={self.connect_timeout}"
            )
        else:
            raise ValueError(f"Неподдерживаемый тип БД: {self.db_type}")


@dataclass
class AppConfig:
    """Главная конфигурация приложения."""
    app_name: str = 'Production Manager'
    app_version: str = '1.0.0'
    debug: bool = False
    db: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Создание конфигурации из переменных окружения."""
        db_config = DatabaseConfig(
            db_type=os.getenv('DB_TYPE', 'sqlite'),
            db_path=os.getenv('DB_PATH', 'db.sqlite3'),
            db_host=os.getenv('DB_HOST', 'localhost'),
            db_port=int(os.getenv('DB_PORT', '5432')),
            db_name=os.getenv('DB_NAME', 'production_db'),
            db_user=os.getenv('DB_USER', ''),
            db_password=os.getenv('DB_PASSWORD', ''),
        )
        return cls(
            debug=os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes'),
            db=db_config,
        )


# Глобальный экземпляр конфигурации
config = AppConfig.from_env()
