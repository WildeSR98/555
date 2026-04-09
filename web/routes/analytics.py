"""
Маршруты страницы Analytics.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from src.database import get_db
from src.models import Device, WorkLog, User, Workplace
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/analytics")
async def analytics_page(request: Request, db: Session = Depends(get_db)):
    """Страница Analytics."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    # Статистика по устройствам
    device_status = db.query(
        Device.status, func.count(Device.id)
    ).group_by(Device.status).all()

    # Работы за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    weekly_work = db.query(
        func.date(WorkLog.created_at), func.count(WorkLog.id)
    ).filter(WorkLog.created_at >= week_ago).group_by(func.date(WorkLog.created_at)).all()

    # Топ пользователей по количеству работ
    top_users = db.query(
        User.username, User.first_name, User.last_name, func.count(WorkLog.id).label('count')
    ).join(WorkLog, WorkLog.worker_id == User.id).group_by(User.id).order_by(func.count(WorkLog.id).desc()).limit(10).all()

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "user": user,
        "device_status": dict(device_status),
        "weekly_work": [{"date": str(row[0]), "count": row[1]} for row in weekly_work],
        "top_users": [{
            "username": row[0],
            "name": f"{row[1]} {row[2]}".strip() or row[0],
            "count": row[3]
        } for row in top_users],
    })
