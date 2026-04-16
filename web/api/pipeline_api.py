"""
API эндпоинты для Pipeline.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db
from src.models import Device

router = APIRouter()


@router.get("/counts")
def get_pipeline_counts(db: Session = Depends(get_db)):
    """Количество устройств по каждому статусу."""
    counts = dict(
        db.query(Device.status, func.count(Device.id))
        .group_by(Device.status).all()
    )
    return counts


@router.get("/devices")
def get_pipeline_devices(
    status: str = Query(...),
    db: Session = Depends(get_db)
):
    """Устройства на конкретном этапе конвейера."""
    from sqlalchemy.orm import joinedload
    devices = db.query(Device).options(
        joinedload(Device.project),
        joinedload(Device.current_worker)
    ).filter(
        Device.status == status
    ).order_by(Device.name).limit(100).all()

    return [
        {
            "id": d.id,
            "code": d.code if hasattr(d, 'code') else None,
            "name": d.name,
            "sn": d.serial_number,
            "pn": d.part_number,
            "project": d.project.name if d.project else "—",
            "worker": d.current_worker.full_name if d.current_worker else "—",
        }
        for d in devices
    ]
