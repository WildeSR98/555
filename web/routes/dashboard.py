"""
Маршруты страницы Dashboard.
Полный функционал как в десктопной версии:
- 4 сводные карточки (всего устройств, завершено сегодня, брак, активные сессии)
- Таблица рабочих мест со статусом
- Таблица активных сессий с длительностью
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

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

    # 4 сводные карточки
    total_devices = db.query(Device).count()

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = db.query(WorkLog).filter(
        WorkLog.action == 'COMPLETED',
        WorkLog.created_at >= today_start
    ).count()

    defects = db.query(Device).filter(Device.status == 'DEFECT').count()

    active_sessions_count = db.query(WorkSession).filter_by(is_active=True).count()

    # Рабочие места со статусом
    workplaces = db.query(Workplace).filter(
        Workplace.is_active == True
    ).order_by(Workplace.order).all()

    workplace_data = []
    for wp in workplaces:
        active_count = db.query(WorkSession).filter(
            WorkSession.workplace_id == wp.id,
            WorkSession.is_active == True
        ).count()
        workplace_data.append({
            "name": wp.name,
            "type": wp.type_display,
            "pool": f"Пул ({wp.pool_limit})" if wp.is_pool else "—",
            "active_count": active_count,
        })

    # Активные сессии
    sessions = db.query(WorkSession).filter(WorkSession.is_active == True).all()
    session_data = []
    now = datetime.now()
    for sess in sessions:
        worker_name = sess.worker.full_name if sess.worker else "?"
        wp_name = sess.workplace.name if sess.workplace else "?"
        start_time = sess.started_at.strftime('%H:%M') if sess.started_at else "?"
        if sess.started_at:
            delta = now - sess.started_at
            mins = int(delta.total_seconds() // 60)
            duration = f"{mins // 60}ч {mins % 60}м" if mins >= 60 else f"{mins}м"
        else:
            duration = "?"
        session_data.append({
            "worker": worker_name,
            "workplace": wp_name,
            "start": start_time,
            "duration": duration,
        })

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total_devices": total_devices,
        "completed_today": completed_today,
        "defects": defects,
        "active_sessions_count": active_sessions_count,
        "workplaces": workplace_data,
        "sessions": session_data,
    })
