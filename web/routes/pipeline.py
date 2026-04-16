"""
Маршруты страницы Pipeline (Конвейер).
Визуальный обзор производственного процесса — карточки этапов с количествами.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db
from src.models import Device
from web.routes.auth import get_current_user
from web.dependencies import render_template
from fastapi_csrf_protect import CsrfProtect
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

# Основные этапы конвейера (Ожидание + Работа)
MAIN_STAGES = [
    ('WAITING_KITTING', 'KITTING', 'Комплектовка'),
    ('WAITING_ASSEMBLY', 'ASSEMBLY', 'Сборка'),
    ('WAITING_VIBROSTAND', 'VIBROSTAND', 'Вибростенд'),
    ('WAITING_TECH_CONTROL_1_1', 'TECH_CONTROL_1_1', 'ОТК 1.1'),
    ('WAITING_TECH_CONTROL_1_2', 'TECH_CONTROL_1_2', 'ОТК 1.2'),
    ('WAITING_FUNC_CONTROL', 'FUNC_CONTROL', 'Тестирование'),
    ('WAITING_TECH_CONTROL_2_1', 'TECH_CONTROL_2_1', 'ОТК 2.1'),
    ('WAITING_TECH_CONTROL_2_2', 'TECH_CONTROL_2_2', 'ОТК 2.2'),
    ('WAITING_PACKING', 'PACKING', 'Упаковка'),
    ('WAITING_ACCOUNTING', 'ACCOUNTING', 'Учёт'),
]

# Дополнительные статусы
EXTRA_STAGES = [
    ('WAREHOUSE', 'Склад'),
    ('QC_PASSED', 'Контроль пройден'),
    ('SHIPPED', 'Отгружено'),
    ('DEFECT', 'Брак'),
    ('WAITING_PARTS', 'Ожид. запчастей'),
    ('WAITING_SOFTWARE', 'Ожид. ПО'),
]


@router.get("/pipeline")
def pipeline_page(request: Request, db: Session = Depends(get_db), csrf_protect: CsrfProtect = Depends()):
    """Страница Pipeline — карточки этапов."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    # Подсчёт по каждому статусу
    status_counts = dict(
        db.query(Device.status, func.count(Device.id))
        .group_by(Device.status).all()
    )

    # Основные этапы
    stages = []
    total = 0
    for w_code, i_code, label in MAIN_STAGES:
        w_count = status_counts.get(w_code, 0)
        i_count = status_counts.get(i_code, 0)
        total += w_count + i_count
        stages.append({
            "label": label,
            "waiting_code": w_code,
            "working_code": i_code,
            "waiting_count": w_count,
            "working_count": i_count,
        })

    # Дополнительные статусы
    extras = []
    for code, label in EXTRA_STAGES:
        count = status_counts.get(code, 0)
        total += count
        extras.append({
            "code": code,
            "label": label,
            "count": count,
        })

    return render_template("pipeline.html", {
        "user": user,
        "stages": stages,
        "extras": extras,
        "total": total,
    }, request, csrf_protect)
