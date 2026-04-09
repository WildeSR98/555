"""
API эндпоинты для Admin.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_session
from src.models import User, WorkLog

router = APIRouter()


@router.get("/users")
async def get_users(db: Session = Depends(get_session)):
    """Получить всех пользователей."""
    users = db.query(User).order_by(User.date_joined.desc()).all()
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "role": u.role,
            "role_display": u.role_display,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "date_joined": u.date_joined.isoformat() if u.date_joined else None,
        }
        for u in users
    ]


@router.get("/stats")
async def get_admin_stats(db: Session = Depends(get_session)):
    """Получить статистику для админки."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter_by(is_active=True).count()
    total_worklogs = db.query(WorkLog).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_worklogs": total_worklogs,
    }
