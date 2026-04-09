"""
API эндпоинты для Analytics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from src.database import get_session
from src.models import Device, WorkLog, User, Workplace

router = APIRouter()


@router.get("/")
async def get_analytics_summary(db: Session = Depends(get_session)):
    """Общая сводка аналитики."""
    # Устройства по статусам
    device_status = db.query(
        Device.status, func.count(Device.id)
    ).group_by(Device.status).all()
    
    # Работы за последние 30 дней
    month_ago = datetime.now() - timedelta(days=30)
    monthly_work = db.query(
        func.date(WorkLog.created_at).label('date'),
        func.count(WorkLog.id).label('count')
    ).filter(WorkLog.created_at >= month_ago).group_by(func.date(WorkLog.created_at)).all()
    
    # Топ пользователей
    top_users = db.query(
        User.id, User.username, User.first_name, User.last_name,
        func.count(WorkLog.id).label('count')
    ).join(WorkLog, WorkLog.user_id == User.id).group_by(User.id).order_by(
        func.count(WorkLog.id).desc()
    ).limit(10).all()
    
    return {
        "device_status": {status: count for status, count in device_status},
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


@router.get("/devices")
async def get_device_analytics(db: Session = Depends(get_session)):
    """Аналитика по устройствам."""
    devices = db.query(
        Device.id, Device.sn, Device.model, Device.status,
        func.count(WorkLog.id).label('work_count')
    ).outerjoin(WorkLog, WorkLog.device_id == Device.id).group_by(Device.id).all()
    
    return [
        {
            "id": row[0],
            "sn": row[1],
            "model": row[2],
            "status": row[3],
            "work_count": row[4],
        }
        for row in devices
    ]


@router.get("/users")
async def get_user_analytics(db: Session = Depends(get_session)):
    """Аналитика по пользователям."""
    users = db.query(User).all()
    result = []
    
    for user in users:
        work_count = db.query(func.count(WorkLog.id)).filter(WorkLog.user_id == user.id).scalar()
        last_work = db.query(WorkLog).filter(WorkLog.user_id == user.id).order_by(WorkLog.created_at.desc()).first()
        
        result.append({
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "role_display": user.role_display,
            "work_count": work_count,
            "last_work_at": last_work.created_at.isoformat() if last_work and last_work.created_at else None,
        })
    
    return result
