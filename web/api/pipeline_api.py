"""
API эндпоинты для Pipeline.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Device

router = APIRouter()


@router.get("/")
async def get_pipeline(db: Session = Depends(get_db)):
    """Получить устройства в производстве."""
    devices = db.query(Device).filter(
        Device.status.in_(['IN_PROGRESS', 'WAITING'])
    ).all()
    
    return [
        {
            "id": d.id,
            "sn": d.serial_number,
            "model": d.name,
            "status": d.status,
            "project_id": d.project_id,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in devices
    ]
