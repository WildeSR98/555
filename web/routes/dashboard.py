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
from web.dependencies import render_template
from fastapi_csrf_protect import CsrfProtect
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/dashboard")
def dashboard_page(request: Request, db: Session = Depends(get_db), csrf_protect: CsrfProtect = Depends()):
    """Страница Dashboard."""
    from sqlalchemy.orm import joinedload
    
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

    # Рабочие места со статусом (Оптимизировано: получаем количество сессий одним запросом)
    session_counts = dict(
        db.query(WorkSession.workplace_id, func.count(WorkSession.id))
        .filter(WorkSession.is_active == True)
        .group_by(WorkSession.workplace_id).all()
    )
    
    workplaces = db.query(Workplace).filter(
        Workplace.is_active == True
    ).order_by(Workplace.order).all()

    workplace_data = []
    for wp in workplaces:
        active_count = session_counts.get(wp.id, 0)
        workplace_data.append({
            "name": wp.name,
            "type": wp.type_display,
            "pool": f"Пул ({wp.pool_limit})" if wp.is_pool else "—",
            "active_count": active_count,
        })

    # Активные сессии (Eager loading worker и workplace)
    sessions = db.query(WorkSession).options(
        joinedload(WorkSession.worker),
        joinedload(WorkSession.workplace)
    ).filter(WorkSession.is_active == True).all()
    
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

    # Распределение по статусам для графика
    status_distribution = dict(
        db.query(Device.status, func.count(Device.id))
        .group_by(Device.status).all()
    )
    
    # Группируем для красоты
    chart_data = {
        "Ожидание": sum(v for k, v in status_distribution.items() if k.startswith('WAITING_')),
        "В работе": sum(v for k, v in status_distribution.items() if k in ('ASSEMBLY', 'PRE_PRODUCTION', 'VIBROSTAND', 'FUNC_CONTROL', 'TECH_CONTROL_1_1', 'TECH_CONTROL_1_2', 'TECH_CONTROL_2_1', 'TECH_CONTROL_2_2', 'PACKING', 'ACCOUNTING')),
        "Готово/Склад": status_distribution.get('WAREHOUSE', 0) + status_distribution.get('QC_PASSED', 0) + status_distribution.get('SHIPPED', 0),
        "Брак/Задержка": status_distribution.get('DEFECT', 0) + status_distribution.get('WAITING_PARTS', 0) + status_distribution.get('WAITING_SOFTWARE', 0),
    }

    # Последние события (логи) (Eager loading device, worker, workplace)
    recent_logs = []
    logs = db.query(WorkLog).options(
        joinedload(WorkLog.device),
        joinedload(WorkLog.worker),
        joinedload(WorkLog.workplace)
    ).order_by(WorkLog.created_at.desc()).limit(8).all()
    
    for l in logs:
        device_sn = "—"
        if l.device:
            device_sn = getattr(l.device, 'serial_number', "—") or "—"
        
        recent_logs.append({
            "time": l.created_at.strftime('%H:%M:%S'),
            "worker": l.worker.username if l.worker else "Система",
            "action": l.action_display,
            "sn": device_sn,
            "workplace": l.workplace.name if l.workplace else "—"
        })

    return render_template("dashboard.html", {
        "user": user,
        "total_devices": total_devices,
        "completed_today": completed_today,
        "defects": defects,
        "active_sessions_count": active_sessions_count,
        "workplaces": workplace_data,
        "sessions": session_data,
        "chart_data": chart_data,
        "recent_logs": recent_logs,
    }, request, csrf_protect)
