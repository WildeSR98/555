from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.database import get_db
from src.logger import logger
import shutil
import os

router = APIRouter()

@router.get("/")
def get_health(db: Session = Depends(get_db)):
    """
    Проверка состояния системы: БД, Диск.
    """
    status = {
        "database": "OK",
        "storage": "OK",
        "version": "1.0.0"
    }
    
    # 1. Проверка БД
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check failed: Database unreachable. Error: {e}")
        status["database"] = "ERROR"

    # 2. Проверка места на диске (где лежит БД)
    try:
        # Получаем путь к БД (упрощенно - текущая директория или из конфига)
        total, used, free = shutil.disk_usage(".")
        free_gb = free / (2**30)
        if free_gb < 0.5: # Менее 500 МБ
            status["storage"] = "LOW_SPACE"
            logger.warning(f"Health check: Low disk space ({free_gb:.2f} GB free)")
        status["free_space_gb"] = round(free_gb, 2)
    except Exception as e:
        logger.error(f"Health check: Could not check disk usage. Error: {e}")
        status["storage"] = "UNKNOWN"

    status["overall"] = "OK" if status["database"] == "OK" and status["storage"] != "ERROR" else "CRITICAL"
    
    return status
