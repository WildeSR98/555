"""
API эндпоинты для SN Pool.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import SerialNumber, Device

router = APIRouter()


@router.get("/")
async def get_serial_numbers(db: Session = Depends(get_db)):
    """Получить все серийные номера."""
    serial_numbers = db.query(SerialNumber).order_by(SerialNumber.created_at.desc()).all()
    
    return [
        {
            "id": sn.id,
            "code": sn.sn,
            "model_id": sn.model_id,
            "is_used": sn.is_used,
            "device_id": sn.device_id,
            "created_at": sn.created_at.isoformat() if sn.created_at else None,
        }
        for sn in serial_numbers
    ]
