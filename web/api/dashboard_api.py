"""
API эндпоинты для Dashboard.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from src.database import get_db
from src.models import Workplace, WorkSession, Device, WorkLog

router = APIRouter()


@router.get("/")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Получить статистику дашборда."""
    total_workplaces = db.query(Workplace).count()
    active_sessions = db.query(WorkSession).filter_by(is_active=True).count()
    total_devices = db.query(Device).count()
    
    # Статистика по статусам устройств
    device_status = db.query(Device.status, func.count(Device.id)).group_by(Device.status).all()
    
    # Последние работы (с eager loading worker и device)
    from sqlalchemy.orm import joinedload
    recent_worklogs = db.query(WorkLog).options(
        joinedload(WorkLog.worker),
        joinedload(WorkLog.device)
    ).order_by(WorkLog.created_at.desc()).limit(10).all()
    
    return {
        "total_workplaces": total_workplaces,
        "active_sessions": active_sessions,
        "total_devices": total_devices,
        "device_status": {status: count for status, count in device_status},
        "recent_worklogs": [
            {
                "id": wl.id,
                "user": wl.worker.full_name if wl.worker else (f"User #{wl.worker_id}" if wl.worker_id else None),
                "device": wl.device.serial_number if wl.device else (f"Device #{wl.device_id}" if wl.device_id else None),
                "action": wl.action,
                "created_at": wl.created_at.isoformat() if wl.created_at else None,
            }
            for wl in recent_worklogs
        ],
    }


@router.get("/chart-data")
def get_chart_data(db: Session = Depends(get_db)):
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
        "workplaces_by_type": {
            wp_type: count 
            for wp_type, count in db.query(
                Workplace.workplace_type, func.count(Workplace.id)
            ).group_by(Workplace.workplace_type).all()
        },
    }


@router.get("/live-stats")
def get_live_stats(db: Session = Depends(get_db)):
    """Лёгкий endpoint — только 4 числа для live-обновления карточек дашборда."""
    from datetime import date
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "total_devices":      db.query(Device).count(),
        "completed_today":    db.query(WorkLog).filter(
            WorkLog.action == 'COMPLETED',
            WorkLog.created_at >= today_start
        ).count(),
        "defects":            db.query(Device).filter(Device.status == 'DEFECT').count(),
        "active_sessions":    db.query(WorkSession).filter_by(is_active=True).count(),
    }
