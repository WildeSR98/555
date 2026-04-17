"""
API эндпоинты для Архива проектов.
Завершённые проекты + история WorkLog по каждому.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from src.database import get_db
from src.models import Project, Device, WorkLog, User, ProjectRoute
from web.dependencies import get_current_user

router = APIRouter()

ARCHIVE_HOLD_DAYS = 30   # минимум дней после завершения


def _get_completion_date(project: Project, db: Session) -> Optional[datetime]:
    """
    Дата завершения: момент когда ПОСЛЕДНЕЕ устройство стало QC_PASSED.
    Ищем в WorkLog последний QC_PASSED для каждого устройства,
    затем берём максимальный.
    """
    devices = project.devices
    if not devices:
        return None
    if not all(d.status == 'QC_PASSED' for d in devices):
        return None

    last_dt = None
    for d in devices:
        log = (
            db.query(WorkLog)
            .filter(WorkLog.device_id == d.id, WorkLog.new_status == 'QC_PASSED')
            .order_by(WorkLog.created_at.desc())
            .first()
        )
        if log:
            if last_dt is None or log.created_at > last_dt:
                last_dt = log.created_at
    return last_dt


def _archive_eligibility(project: Project, db: Session) -> dict:
    """Возвращает статус архивируемости и оставшиеся дни."""
    if project.status == 'ARCHIVED':
        return {"eligible": False, "reason": "already_archived"}

    completion_date = _get_completion_date(project, db)
    if completion_date is None:
        return {"eligible": False, "reason": "not_completed", "days_left": None}

    days_passed = (datetime.now() - completion_date).days
    days_left = ARCHIVE_HOLD_DAYS - days_passed
    if days_left > 0:
        return {"eligible": False, "reason": "hold_period", "days_left": days_left}

    return {"eligible": True, "reason": None, "days_left": 0}


@router.get("/projects")
def list_archive_projects(db: Session = Depends(get_db)):
    """Список проектов в архиве."""
    projects = db.query(Project).filter_by(status='ARCHIVED').order_by(Project.updated_at.desc()).all()
    result = []
    for p in projects:
        devices = p.devices
        result.append({
            "id":            p.id,
            "name":          p.name,
            "code":          p.code,
            "manager":       p.manager.full_name if p.manager else "—",
            "device_count":  len(devices),
            "archived_at":   p.updated_at.strftime('%d.%m.%Y') if p.updated_at else "—",
        })
    return result


@router.get("/projects/{project_id}/logs")
def get_project_logs(project_id: int, db: Session = Depends(get_db)):
    """История WorkLog для всех устройств проекта."""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")

    devices = project.devices
    result = []
    for d in devices:
        logs = (
            db.query(WorkLog)
            .filter(WorkLog.device_id == d.id)
            .order_by(WorkLog.created_at.asc())
            .all()
        )
        result.append({
            "device_id":     d.id,
            "device_name":   d.name,
            "serial_number": d.serial_number,
            "status":        d.status,
            "logs": [
                {
                    "id":          l.id,
                    "action":      l.action_display,
                    "old_status":  Device.STATUS_DISPLAY.get(l.old_status, l.old_status),
                    "new_status":  Device.STATUS_DISPLAY.get(l.new_status, l.new_status),
                    "worker":      l.worker.full_name if l.worker else "—",
                    "workplace":   l.workplace.name if l.workplace else "—",
                    "notes":       l.notes or "",
                    "created_at":  l.created_at.strftime('%d.%m.%Y %H:%M') if l.created_at else "—",
                }
                for l in logs
            ]
        })
    return result


@router.get("/projects/{project_id}/eligibility")
def check_eligibility(project_id: int, db: Session = Depends(get_db)):
    """Проверить, можно ли архивировать проект."""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")
    return _archive_eligibility(project, db)


@router.post("/projects/{project_id}")
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Архивировать проект (ручной режим, с проверкой условий)."""
    if user.role not in ('ADMIN', 'ROOT', 'MANAGER'):
        raise HTTPException(403, "Недостаточно прав")

    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")

    elig = _archive_eligibility(project, db)
    if not elig["eligible"]:
        reason = elig.get("reason")
        days_left = elig.get("days_left")
        if reason == "already_archived":
            raise HTTPException(400, "Проект уже в архиве")
        if reason == "not_completed":
            raise HTTPException(400, "Не все устройства завершены (QC_PASSED)")
        if reason == "hold_period":
            raise HTTPException(400, f"Архивирование доступно через {days_left} дн. В архив можно только через 30 дней после завершения.")

    project.status = 'ARCHIVED'
    project.updated_at = datetime.now()
    db.commit()
    return {"ok": True, "message": f"Проект «{project.name}» перемещён в архив"}
