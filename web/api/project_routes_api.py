"""
API для управления маршрутными листами на уровне проекта.

Логика:
  - Каждый проект может иметь индивидуальные маршруты по типам устройств.
  - Если индивидуальный маршрут не задан → используется глобальный RouteConfig
    для данного device_type (или дефолтный).
  - Изменения сохраняются в pm_project_route_stage и не влияют на другие проекты.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
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
    """Human-readable label for a stage key. Handles KEY::N duplicates."""
    if stored_label:
        return stored_label
    # Strip ::N suffix for duplicate stages (e.g. FUNC_CONTROL::2 -> FUNC_CONTROL)
    base_key = stage_key.split('::')[0] if '::' in stage_key else stage_key
    n = int(stage_key.split('::')[1]) if '::' in stage_key else None
    hit = next((lbl for k, lbl, _ in ROUTE_PIPELINE_STAGES if k == base_key), None)
    if hit:
        return f"{hit}-{n}" if n else hit
    if base_key.startswith('CUSTOM::'):
        return base_key[8:]
    return stage_key


# Mapping from ROUTE stage_key base -> Device.status values meaning "at this stage"
_STAGE_STATUSES: dict[str, list[str]] = {
    'KITTING':          ['WAITING_KITTING', 'WAITING_PRE_PRODUCTION', 'PRE_PRODUCTION'],
    'ASSEMBLY':         ['WAITING_ASSEMBLY', 'ASSEMBLY'],
    'VIBROSTAND':       ['WAITING_VIBROSTAND', 'VIBROSTAND'],
    'TECH_CONTROL_1_1': ['WAITING_TECH_CONTROL_1_1', 'TECH_CONTROL_1_1'],
    'TECH_CONTROL_1_2': ['WAITING_TECH_CONTROL_1_2', 'TECH_CONTROL_1_2'],
    'FUNC_CONTROL':     ['WAITING_FUNC_CONTROL', 'FUNC_CONTROL'],
    'TECH_CONTROL_2_1': ['WAITING_TECH_CONTROL_2_1', 'TECH_CONTROL_2_1'],
    'TECH_CONTROL_2_2': ['WAITING_TECH_CONTROL_2_2', 'TECH_CONTROL_2_2'],
    'PACKING':          ['WAITING_PACKING', 'PACKING'],
    'ACCOUNTING':       ['WAITING_ACCOUNTING', 'ACCOUNTING'],
    'WAREHOUSE':        ['WAITING_WAREHOUSE', 'WAREHOUSE'],
}


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
    """Список активных проектов с устройствами (для аккордеона во вкладке Проекты)."""
    projects = (
        db.query(Project)
        .filter(Project.status != 'ARCHIVED')
        .order_by(Project.name)
        .all()
    )
    result = []
    for p in projects:
        # Уникальные типы устройств в проекте (включая None → заменяем на 'UNKNOWN')
        types_q = (
            db.query(Device.device_type)
            .filter(Device.project_id == p.id)
            .distinct()
            .all()
        )
        device_types = [t[0] or 'UNKNOWN' for t in types_q]

        if not device_types:
            continue  # Проекты без устройств скрываем

        result.append({
            "id":             p.id,
            "name":           p.name,
            "code":           p.code or "",
            "status":         p.status,
            "status_display": p.status_display,
            "device_types":   device_types,
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
            label=s.label or None,  # save for any stage (renames, ::N auto-labels)
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


@router.get("/{project_id}/device/{device_type}/check-remove")
def check_remove_stage(
    project_id: int,
    device_type: str,
    stage: str = Query(..., description="stage_key being removed"),
    db: Session = Depends(get_db),
):
    """
    Проверяет, сколько устройств окажутся "в подвешенном состоянии"
    если этот этап удалить из маршрута проекта.
    Возвращает список затронутых устройств (до 10).
    """
    # Strip ::N from duplicate stages (e.g. FUNC_CONTROL::2 -> FUNC_CONTROL)
    base_key = stage.split('::')[0] if '::' in stage else stage

    affected_statuses = _STAGE_STATUSES.get(base_key, [f'WAITING_{base_key}', base_key])

    devices = (
        db.query(Device)
        .filter(
            Device.project_id == project_id,
            Device.device_type == device_type,
            Device.status.in_(affected_statuses),
        )
        .all()
    )

    return {
        "affected_count":  len(devices),
        "device_serials":  [d.serial_number or f"#{d.id}" for d in devices[:10]],
        "has_more":        len(devices) > 10,
    }
