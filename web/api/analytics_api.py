"""
API эндпоинты для Analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from src.database import get_db
from src.models import Device, WorkLog, User, Workplace

router = APIRouter()


@router.get("/")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Общая сводка аналитики."""
    # Устройства по статусам
    device_status = db.query(
        Device.status, func.count(Device.id)
    ).group_by(Device.status).all()
    
    # Стилизуем ключи
    status_map = {}
    for st, count in device_status:
        display = Device.STATUS_DISPLAY.get(st, st)
        status_map[display] = count
    
    # Работы за последние 30 дней
    month_ago = datetime.now() - timedelta(days=30)
    monthly_work = db.query(
        func.date(WorkLog.created_at).label('date'),
        func.count(WorkLog.id).label('count')
    ).filter(WorkLog.created_at >= month_ago, WorkLog.action == 'COMPLETED').group_by(func.date(WorkLog.created_at)).all()
    
    # Топ пользователей
    top_users = db.query(
        User.id, User.username, User.first_name, User.last_name,
        func.count(WorkLog.id).label('count')
    ).join(WorkLog, WorkLog.worker_id == User.id).group_by(User.id).order_by(
        func.count(WorkLog.id).desc()
    ).limit(10).all()
    
    return {
        "device_status": status_map,
        "monthly_work": [
            {"date": str(row[0]), "count": row[1]} 
            for row in monthly_work
        ],
        "top_users": [
            {
                "id": row[0],
                "username": row[1],
                "name": f"{row[2]} {row[3]}".strip() or row[1],
                "count": row[4],
            }
            for row in top_users
        ],
    }


@router.get("/employee")
async def get_employee_analytics(
    user_id: int = Query(...),
    period: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Аналитика по конкретному сотруднику с фильтром по времени."""
    now = datetime.now()
    cutoff = None
    
    if period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
        
    query = db.query(WorkLog).filter(WorkLog.worker_id == user_id)
    if cutoff:
        query = query.filter(WorkLog.created_at >= cutoff)
        
    logs = query.order_by(WorkLog.created_at.desc()).all()
    
    # Подсчет статистики
    stats = {
        "completed": 0,
        "defect": 0,
        "scan_in": 0
    }
    
    ACTION_MAP = {
        'SCAN_IN': 'Взято в работу',
        'COMPLETED': 'Завершено',
        'DEFECT': 'Брак',
        'KEPT': 'Оставлено',
        'MAKE_SEMIFINISHED': 'Отправлено в ПФ'
    }
    
    history = []
    for log in logs:
        if log.action == 'COMPLETED':
            stats["completed"] += 1
        elif log.action == 'DEFECT':
            stats["defect"] += 1
        elif log.action == 'SCAN_IN':
            stats["scan_in"] += 1
            
        history.append({
            "id": log.id,
            "created_at": log.created_at.strftime('%d.%m.%Y %H:%M:%S') if log.created_at else "—",
            "action": ACTION_MAP.get(log.action, log.action),
            "sn": log.device.serial_number if log.device and log.device.serial_number else (log.device.part_number if log.device else "—"),
            "project": log.project.name if log.project else "—",
            "workplace": log.workplace.name if log.workplace else "—"
        })
        
    return {
        "stats": stats,
        "history": history
    }
