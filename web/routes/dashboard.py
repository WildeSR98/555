"""
Маршруты страницы Dashboard.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db
from src.models import Workplace, WorkSession, Device, WorkLog
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/dashboard")
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    """Страница Dashboard."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    # Статистика
    total_workplaces = db.query(Workplace).count()
    active_sessions = db.query(WorkSession).filter_by(is_active=True).count()
    total_devices = db.query(Device).count()
    
    # Последние работы
    recent_worklogs = db.query(WorkLog).order_by(WorkLog.created_at.desc()).limit(10).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total_workplaces": total_workplaces,
        "active_sessions": active_sessions,
        "total_devices": total_devices,
        "recent_worklogs": recent_worklogs,
    })
