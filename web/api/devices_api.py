"""
API эндпоинты для Devices.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db
from src.models import Device, WorkLog

router = APIRouter()


@router.get("/")
async def get_devices(
    search: str = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    """Получить все устройства с фильтрацией."""
    query = db.query(Device)
    
    if search:
        query = query.filter(Device.serial_number.ilike(f"%{search}%"))
    if status:
        query = query.filter(Device.status == status)
    
    devices = query.order_by(Device.created_at.desc()).all()
    
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


@router.get("/statuses")
async def get_device_statuses(db: Session = Depends(get_db)):
    """Получить список статусов с количеством."""
    statuses = db.query(Device.status, func.count(Device.id)).group_by(Device.status).all()
    return {status: count for status, count in statuses}
