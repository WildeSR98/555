"""
API эндпоинты для Dashboard.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from src.database import get_session
from src.models import Workplace, WorkSession, Device, WorkLog

router = APIRouter()


@router.get("/")
async def get_dashboard_stats(db: Session = Depends(get_session)):
    """Получить статистику дашборда."""
    total_workplaces = db.query(Workplace).count()
    active_sessions = db.query(WorkSession).filter_by(is_active=True).count()
    total_devices = db.query(Device).count()
    
    # Статистика по статусам устройств
    device_status = db.query(Device.status, func.count(Device.id)).group_by(Device.status).all()
    
    # Последние работы
    recent_worklogs = db.query(WorkLog).order_by(WorkLog.created_at.desc()).limit(10).all()
    
    return {
        "total_workplaces": total_workplaces,
        "active_sessions": active_sessions,
        "total_devices": total_devices,
        "device_status": {status: count for status, count in device_status},
        "recent_worklogs": [
            {
                "id": wl.id,
                "user": wl.worker.full_name if wl.worker else None,
                "device": wl.device.serial_number if wl.device else None,
                "action": wl.action,
                "created_at": wl.created_at.isoformat() if wl.created_at else None,
            }
            for wl in recent_worklogs
        ],
    }


@router.get("/chart-data")
async def get_chart_data(db: Session = Depends(get_session)):
    """Данные для графиков дашборда."""
    # Активность за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    daily_activity = db.query(
        func.date(WorkLog.created_at).label('date'),
        func.count(WorkLog.id).label('count')
    ).filter(WorkLog.created_at >= week_ago).group_by(func.date(WorkLog.created_at)).all()
    
    return {
        "daily_activity": [
            {"date": str(row[0]), "count": row[1]} 
            for row in daily_activity
        ],
        "workplaces_by_status": {
            status: count 
            for status, count in db.query(
                Workplace.status, func.count(Workplace.id)
            ).group_by(Workplace.status).all()
        },
    }
