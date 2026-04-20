"""
API для управления маршрутными листами на уровне проекта.

Логика:
  - Каждый проект может иметь индивидуальные маршруты по типам устройств.
  - Если индивидуальный маршрут не задан → используется глобальный RouteConfig
    для данного device_type (или дефолтный).
  - Изменения сохраняются в pm_project_route_stage и не влияют на другие проекты.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.database import get_db
from src.models import (
    Project, Device, DeviceModel, DeviceCategory,
    RouteConfig, RouteConfigStage, ProjectRouteStage,
    ROUTE_PIPELINE_STAGES,
)
from web.ws_manager import manager as ws_manager

router = APIRouter()


# ──────────────────────── Helpers ────────────────────────

def _resolve_label(stage_key: str, stored_label: Optional[str] = None) -> str:
    """Human-readable label for a stage key."""
    if stored_label:
        return stored_label
    hit = next((lbl for k, lbl, _ in ROUTE_PIPELINE_STAGES if k == stage_key), None)
    if hit:
        return hit
    if stage_key.startswith('CUSTOM::'):
        return stage_key[8:]
    return stage_key


def _get_global_stages(device_type: str, db: Session) -> list:
    """Receive stages from the global RouteConfig for the given device_type."""
    rc = (
        db.query(RouteConfig).filter_by(device_type=device_type).first()
        or db.query(RouteConfig).filter_by(is_default=True).first()
    )
    if not rc:
        return []
    return [
        {
            "stage_key":   s.stage_key,
            "label":       _resolve_label(s.stage_key),
            "order_index": s.order_index,
            "is_enabled":  s.is_enabled,
            "is_custom":   s.stage_key.startswith('CUSTOM::'),
        }
        for s in rc.stages
    ]


def _get_project_stages(project_id: int, device_type: str, db: Session) -> tuple[list, bool]:
    """
    Returns (stages_list, is_overridden).
    Falls back to global config if no project-specific override exists.
    """
    overrides = (
        db.query(ProjectRouteStage)
        .filter_by(project_id=project_id, device_type=device_type)
        .order_by(ProjectRouteStage.order_index)
        .all()
    )
    if overrides:
        return ([
            {
                "stage_key":   s.stage_key,
                "label":       _resolve_label(s.stage_key, s.label),
                "order_index": s.order_index,
                "is_enabled":  s.is_enabled,
                "is_custom":   s.stage_key.startswith('CUSTOM::'),
            }
            for s in overrides
        ], True)

    return _get_global_stages(device_type, db), False


# ──────────────────────── Schemas ────────────────────────

class StageOverrideItem(BaseModel):
    stage_key:   str
    is_enabled:  bool
    order_index: int
    label:       Optional[str] = None


class SaveProjectRouteBody(BaseModel):
    stages: List[StageOverrideItem]


# ──────────────────────── Endpoints ────────────────────────

@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    """Список проектов с кол-вом типов устройств (для аккордеона во вкладке Проекты)."""
    projects = db.query(Project).order_by(Project.name).all()
    result = []
    for p in projects:
        # Уникальные типы устройств в проекте
        types_q = (
            db.query(Device.device_type)
            .filter(Device.project_id == p.id)
            .distinct()
            .all()
        )
        device_types = [t[0] for t in types_q if t[0]]

        if not device_types:
            continue  # Проекты без устройств скрываем

        result.append({
            "id":     p.id,
            "name":   p.name,
            "code":   p.code or "",
            "status": p.status,
            "status_display": p.status_display,
            "device_types": device_types,
        })
    return result


@router.get("/{project_id}/device/{device_type}")
def get_project_device_route(project_id: int, device_type: str, db: Session = Depends(get_db)):
    """Этапы маршрута для конкретного проекта + тип устройства."""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")

    stages, is_override = _get_project_stages(project_id, device_type, db)

    # Отображаемое имя типа
    cat = db.query(DeviceCategory).filter_by(code=device_type).first()
    type_display = cat.display_name if cat else device_type

    # Кол-во устройств данного типа в проекте
    device_count = (
        db.query(func.count(Device.id))
        .filter(Device.project_id == project_id, Device.device_type == device_type)
        .scalar()
    )

    return {
        "project_id":    project_id,
        "project_name":  project.name,
        "device_type":   device_type,
        "type_display":  type_display,
        "device_count":  device_count,
        "is_override":   is_override,
        "stages":        stages,
    }


@router.put("/{project_id}/device/{device_type}")
async def save_project_device_route(
    project_id: int,
    device_type: str,
    body: SaveProjectRouteBody,
    db:  Session = Depends(get_db),
):
    """Сохранить индивидуальный маршрут для проекта + тип устройства."""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")

    # Удаляем старые overrides
    db.query(ProjectRouteStage).filter_by(
        project_id=project_id, device_type=device_type
    ).delete()

    # Создаём новые
    for s in body.stages:
        db.add(ProjectRouteStage(
            project_id=project_id,
            device_type=device_type,
            stage_key=s.stage_key,
            order_index=s.order_index,
            is_enabled=s.is_enabled,
            label=s.label if s.stage_key.startswith('CUSTOM::') else None,
        ))

    db.commit()
    await ws_manager.broadcast({
        "type":         "project_route_saved",
        "project_id":   project_id,
        "project_name": project.name,
        "device_type":  device_type,
    })
    return {"ok": True, "message": "Маршрут проекта сохранён"}


@router.delete("/{project_id}/device/{device_type}")
def reset_project_device_route(project_id: int, device_type: str, db: Session = Depends(get_db)):
    """Сбросить индивидуальный маршрут проекта до глобального (удалить overrides)."""
    deleted = (
        db.query(ProjectRouteStage)
        .filter_by(project_id=project_id, device_type=device_type)
        .delete()
    )
    db.commit()
    return {"ok": True, "reset": deleted > 0, "message": "Сброшено до глобального маршрута"}
