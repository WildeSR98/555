"""
API эндпоинты для маршрутных листов.
CRUD конфигураций маршрутов производства + назначение проектам.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from src.database import get_db
from src.models import (
    RouteConfig, RouteConfigStage, RouteConfigEditor,
    ProjectRoute, ROUTE_PIPELINE_STAGES, User, Project
)
from web.dependencies import get_current_user

router = APIRouter()


# ─────────────────── helpers ───────────────────

def _can_edit(user: User, rc: RouteConfig, db: Session) -> bool:
    """Может ли пользователь редактировать маршрут."""
    if user.role in ('ADMIN', 'ROOT', 'MANAGER'):
        return True
    return db.query(RouteConfigEditor).filter_by(
        route_config_id=rc.id, user_id=user.id
    ).first() is not None


def _serialize(rc: RouteConfig) -> dict:
    return {
        "id":          rc.id,
        "name":        rc.name,
        "description": rc.description or "",
        "device_type": rc.device_type,
        "is_default":  rc.is_default,
        "created_at":  rc.created_at.strftime('%d.%m.%Y') if rc.created_at else None,
        "stages": [
            {
                "stage_key":   s.stage_key,
                "order_index": s.order_index,
                "is_enabled":  s.is_enabled,
                "label":       next((lbl for k, lbl, _ in ROUTE_PIPELINE_STAGES if k == s.stage_key), s.stage_key),
            }
            for s in rc.stages
        ],
        "editors": [{"user_id": e.user_id, "username": e.user.username} for e in rc.editors],
    }


# ─────────────────── Pydantic schemas ───────────────────

class StageInput(BaseModel):
    stage_key: str
    is_enabled: bool


class RouteConfigCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    device_type: Optional[str] = None
    stages: Optional[List[StageInput]] = None   # если None — все enabled


class RouteConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    device_type: Optional[str] = None
    stages: Optional[List[StageInput]] = None


class AssignRouteRequest(BaseModel):
    route_config_id: int


class EditorRequest(BaseModel):
    user_id: int


# ─────────────────── Endpoints ───────────────────

@router.get("")
def list_route_configs(db: Session = Depends(get_db)):
    """Список всех маршрутных листов."""
    configs = db.query(RouteConfig).order_by(RouteConfig.is_default.desc(), RouteConfig.id).all()
    return [_serialize(rc) for rc in configs]


@router.post("")
def create_route_config(
    data: RouteConfigCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Создать новый маршрутный лист (на основе дефолтного — все этапы enabled)."""
    if user.role not in ('ADMIN', 'ROOT', 'MANAGER'):
        raise HTTPException(403, "Недостаточно прав")

    rc = RouteConfig(
        name=data.name,
        description=data.description or "",
        device_type=data.device_type,
        is_default=False,
        created_at=datetime.now(),
        created_by_id=user.id,
    )
    db.add(rc)
    db.flush()

    # Этапы: если переданы — используем, иначе все enabled (шаблон дефолтного)
    stages_input = data.stages or [
        StageInput(stage_key=k, is_enabled=True)
        for k, _, _ in ROUTE_PIPELINE_STAGES
    ]
    for s in stages_input:
        idx = next((i for k, _, i in ROUTE_PIPELINE_STAGES if k == s.stage_key), 99)
        db.add(RouteConfigStage(
            route_config_id=rc.id,
            stage_key=s.stage_key,
            order_index=idx,
            is_enabled=s.is_enabled,
        ))

    db.commit()
    db.refresh(rc)
    return {"ok": True, "id": rc.id, "message": f"Маршрут «{rc.name}» создан"}


@router.get("/by-device-type/{device_type}")
def get_by_device_type(device_type: str, db: Session = Depends(get_db)):
    """Маршрут для конкретного типа устройства (или дефолтный)."""
    rc = db.query(RouteConfig).filter_by(device_type=device_type).first()
    if not rc:
        rc = db.query(RouteConfig).filter_by(is_default=True).first()
    if not rc:
        return None
    return _serialize(rc)


@router.get("/{config_id}")
def get_route_config(config_id: int, db: Session = Depends(get_db)):
    """Детали маршрутного листа."""
    rc = db.query(RouteConfig).get(config_id)
    if not rc:
        raise HTTPException(404, "Маршрут не найден")
    return _serialize(rc)


@router.put("/{config_id}")
def update_route_config(
    config_id: int,
    data: RouteConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Обновить маршрутный лист."""
    rc = db.query(RouteConfig).get(config_id)
    if not rc:
        raise HTTPException(404, "Маршрут не найден")
    if rc.is_default:
        raise HTTPException(400, "Дефолтный маршрут нельзя редактировать")
    if not _can_edit(user, rc, db):
        raise HTTPException(403, "Недостаточно прав")

    if data.name is not None:        rc.name = data.name
    if data.description is not None: rc.description = data.description
    if data.device_type is not None: rc.device_type = data.device_type

    if data.stages is not None:
        # Полная замена этапов
        for st in rc.stages:
            db.delete(st)
        db.flush()
        for s in data.stages:
            idx = next((i for k, _, i in ROUTE_PIPELINE_STAGES if k == s.stage_key), 99)
            db.add(RouteConfigStage(
                route_config_id=rc.id,
                stage_key=s.stage_key,
                order_index=idx,
                is_enabled=s.is_enabled,
            ))

    db.commit()
    return {"ok": True, "message": f"Маршрут «{rc.name}» обновлён"}


@router.delete("/{config_id}")
def delete_route_config(
    config_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Удалить маршрутный лист."""
    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, "Только администратор или root могут удалять маршруты")
    rc = db.query(RouteConfig).get(config_id)
    if not rc:
        raise HTTPException(404, "Маршрут не найден")
    if rc.is_default:
        raise HTTPException(400, "Дефолтный маршрут нельзя удалить")
    db.delete(rc)
    db.commit()
    return {"ok": True, "message": f"Маршрут «{rc.name}» удалён"}


@router.put("/project/{project_id}")
def assign_route_to_project(
    project_id: int,
    data: AssignRouteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Назначить / изменить маршрут проекта."""
    if user.role not in ('ADMIN', 'ROOT', 'MANAGER'):
        raise HTTPException(403, "Недостаточно прав")
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")
    rc = db.query(RouteConfig).get(data.route_config_id)
    if not rc:
        raise HTTPException(404, "Маршрут не найден")

    pr = db.query(ProjectRoute).filter_by(project_id=project_id).first()
    if pr:
        pr.route_config_id = data.route_config_id
        pr.assigned_at = datetime.now()
        pr.assigned_by_id = user.id
    else:
        pr = ProjectRoute(
            project_id=project_id,
            route_config_id=data.route_config_id,
            assigned_at=datetime.now(),
            assigned_by_id=user.id,
        )
        db.add(pr)
    db.commit()
    return {"ok": True, "message": f"Маршрут «{rc.name}» назначен проекту"}


@router.get("/project/{project_id}")
def get_project_route(project_id: int, db: Session = Depends(get_db)):
    """Маршрут конкретного проекта."""
    pr = db.query(ProjectRoute).filter_by(project_id=project_id).first()
    if not pr or not pr.route_config:
        # Дефолтный
        rc = db.query(RouteConfig).filter_by(is_default=True).first()
        return _serialize(rc) if rc else None
    return _serialize(pr.route_config)


@router.post("/{config_id}/editors")
def add_editor(
    config_id: int,
    data: EditorRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Выдать права редактора на маршрут."""
    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, "Только администратор или root")
    rc = db.query(RouteConfig).get(config_id)
    if not rc:
        raise HTTPException(404, "Маршрут не найден")
    exists = db.query(RouteConfigEditor).filter_by(
        route_config_id=config_id, user_id=data.user_id
    ).first()
    if not exists:
        db.add(RouteConfigEditor(route_config_id=config_id, user_id=data.user_id))
        db.commit()
    return {"ok": True, "message": "Права выданы"}


@router.delete("/{config_id}/editors/{user_id}")
def remove_editor(
    config_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Отозвать права редактора."""
    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, "Только администратор или root")
    db.query(RouteConfigEditor).filter_by(
        route_config_id=config_id, user_id=user_id
    ).delete()
    db.commit()
    return {"ok": True, "message": "Права отозваны"}
