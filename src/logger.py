import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Папка для логов в корне проекта
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "production_manager.log")

def setup_logger(name="prod_manager"):
    """
    Настройка централизованного логгера с выводом в файл и консоль.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler: Ротация файлов (5MB на файл, до 5 старых копий)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler: Консоль (только если еще нет)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

# Дефолтный экземпляр
logger = setup_logger()
