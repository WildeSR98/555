"""
API эндпоинты для поиска устройств и просмотра истории.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.database import get_db
from src.models import Device, WorkLog

router = APIRouter()


@router.get("/search")
async def search_device(sn: str = Query(...), db: Session = Depends(get_db)):
    """Поиск устройства по SN и возврат его истории логов."""
    # Ищем точное совпадение
    device = db.query(Device).filter(Device.serial_number == sn).first()
    
    # Если не нашли, ищем частичное
    if not device:
        device = db.query(Device).filter(Device.serial_number.contains(sn)).first()
        
    if not device:
        raise HTTPException(404, f"Устройство с SN '{sn}' не найдено")

    # Формируем карточку
    device_card = {
        "id": device.id,
        "name": device.name,
        "sn": device.serial_number,
        "pn": device.part_number,
        "type": device.device_type_display,
        "status": device.status,
        "status_display": device.status_display,
        "badge_color": Device.STATUS_COLORS.get(device.status, '#6c757d'),
        "project": device.project.name if device.project else "—",
        "worker": device.current_worker.full_name if device.current_worker else "—",
        "is_semifinished": device.is_semifinished,
        "location": device.location or "—",
        "created_at": device.created_at.strftime('%d.%m.%Y %H:%M') if device.created_at else "—",
    }

    # Подгружаем историю (WorkLog)
    logs = db.query(WorkLog).filter(
        WorkLog.device_id == device.id
    ).order_by(WorkLog.created_at.desc()).all()

    ACTION_MAP = {
        'SCAN_IN': 'Взято в работу',
        'COMPLETED': 'Завершено',
        'DEFECT': 'Брак',
        'KEPT': 'Оставлено',
        'MAKE_SEMIFINISHED': 'Отправлено в полуфабрикат'
    }

    history = []
    for log in logs:
        action_name = ACTION_MAP.get(log.action, log.action)
        history.append({
            "id": log.id,
            "created_at": log.created_at.strftime('%d.%m.%Y %H:%M:%S') if log.created_at else "—",
            "action": action_name,
            "workplace": log.workplace.name if log.workplace else "—",
            "worker": log.worker.full_name if log.worker else "—",
            "status_change": f"{Device.STATUS_DISPLAY.get(log.old_status, log.old_status)} → {Device.STATUS_DISPLAY.get(log.new_status, log.new_status)}",
            "notes": log.notes or ""
        })

    return {
        "ok": True,
        "device": device_card,
        "history": history
    }
