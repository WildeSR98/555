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
    WorkLog, Workplace, User,
    ROUTE_PIPELINE_STAGES,
)
from web.ws_manager import manager as ws_manager
from web.dependencies import get_current_user

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

# Порядок этапов конвейера (route stage_key)
_PIPELINE_ORDER = [
    'KITTING', 'ASSEMBLY', 'VIBROSTAND',
    'TECH_CONTROL_1_1', 'TECH_CONTROL_1_2',
    'FUNC_CONTROL',
    'TECH_CONTROL_2_1', 'TECH_CONTROL_2_2',
    'PACKING', 'ACCOUNTING', 'WAREHOUSE',
]

# Device.status (ожидание / в работе) → базовый route stage_key
_DEVICE_STATUS_TO_ROUTE_KEY: dict[str, str] = {
    'WAITING_KITTING':           'KITTING',
    'WAITING_PRE_PRODUCTION':    'KITTING',
    'PRE_PRODUCTION':            'KITTING',
    'WAITING_ASSEMBLY':          'ASSEMBLY',
    'ASSEMBLY':                  'ASSEMBLY',
    'WAITING_VIBROSTAND':        'VIBROSTAND',
    'VIBROSTAND':                'VIBROSTAND',
    'WAITING_TECH_CONTROL_1_1':  'TECH_CONTROL_1_1',
    'TECH_CONTROL_1_1':          'TECH_CONTROL_1_1',
    'WAITING_TECH_CONTROL_1_2':  'TECH_CONTROL_1_2',
    'TECH_CONTROL_1_2':          'TECH_CONTROL_1_2',
    'WAITING_FUNC_CONTROL':      'FUNC_CONTROL',
    'FUNC_CONTROL':              'FUNC_CONTROL',
    'WAITING_TECH_CONTROL_2_1':  'TECH_CONTROL_2_1',
    'TECH_CONTROL_2_1':          'TECH_CONTROL_2_1',
    'WAITING_TECH_CONTROL_2_2':  'TECH_CONTROL_2_2',
    'TECH_CONTROL_2_2':          'TECH_CONTROL_2_2',
    'WAITING_PACKING':           'PACKING',
    'PACKING':                   'PACKING',
    'WAITING_ACCOUNTING':        'ACCOUNTING',
    'ACCOUNTING':                'ACCOUNTING',
    'WAITING_WAREHOUSE':         'WAREHOUSE',
    'WAREHOUSE':                 'WAREHOUSE',
}


def _advance_stranded_devices(
    project_id: int,
    device_type: str,
    enabled_keys: set,
    db: Session,
    worker_id: Optional[int] = None,
) -> list:
    """
    Проверяет устройства в проекте после изменения маршрута:
    если устройство ожидает этап, которого больше нет в маршруте → переводится
    на следующий активный этап автоматически.
    Создаёт запись в истории WorkLog для каждого изменения.
    Возвращает список изменений для отображения в UI.
    """
    devices = (
        db.query(Device)
        .filter(Device.project_id == project_id, Device.device_type == device_type)
        .all()
    )

    # Ищем любое активное рабочее место для WorkLog (FK обязательно)
    fallback_wp = db.query(Workplace).filter_by(is_active=True).order_by(Workplace.order).first()
    fallback_wp_id = fallback_wp.id if fallback_wp else None

    # Если не передан worker_id — берём первого админа/ROOT
    if not worker_id:
        su = db.query(User).filter(User.role.in_(['ROOT', 'ADMIN'])).order_by(User.id).first()
        worker_id = su.id if su else None

    advanced = []
    for device in devices:
        route_key = _DEVICE_STATUS_TO_ROUTE_KEY.get(device.status)
        if route_key is None:
            continue  # статус не связан с этапами маршрута

        if route_key in enabled_keys:
            continue  # этап всё ещё есть в маршруте — всё ок

        # Этап удалён — ищем следующий активный
        try:
            idx = _PIPELINE_ORDER.index(route_key)
        except ValueError:
            continue

        next_key = next(
            (k for k in _PIPELINE_ORDER[idx + 1:] if k in enabled_keys),
            None
        )

        old_status = device.status
        device.status = f'WAITING_{next_key}' if next_key else 'QC_PASSED'
        device.updated_at = datetime.now()

        # Запись в истории производственных действий
        if worker_id and fallback_wp_id:
            db.add(WorkLog(
                worker_id=worker_id,
                session_id=None,
                workplace_id=fallback_wp_id,
                device_id=device.id,
                project_id=project_id,
                action='ROUTE_CHANGE',
                old_status=old_status,
                new_status=device.status,
                serial_number=device.serial_number or '',
                notes=f'Автоматический перевод: этап «{route_key}» удалён из маршрута проекта',
                created_at=datetime.now(),
            ))

        advanced.append({
            'serial':    device.serial_number or f'#{device.id}',
            'from':      old_status,
            'to':        device.status,
            'next_stage': next_key or 'завершено',
        })

    return advanced


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
            "stage_key":      s.stage_key,
            "label":          _resolve_label(s.stage_key),
            "order_index":    s.order_index,
            "is_enabled":     s.is_enabled,
            "timer_seconds":  s.timer_seconds if s.timer_seconds is not None else 300,
            "is_custom":      s.stage_key.startswith('CUSTOM::'),
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
                "stage_key":     s.stage_key,
                "label":         _resolve_label(s.stage_key, s.label),
                "order_index":   s.order_index,
                "is_enabled":    s.is_enabled,
                "timer_seconds": s.timer_seconds if s.timer_seconds is not None else 300,
                "is_custom":     s.stage_key.startswith('CUSTOM::'),
            }
            for s in overrides
        ], True)

    return _get_global_stages(device_type, db), False


# ──────────────────────── Schemas ────────────────────────

class StageOverrideItem(BaseModel):
    stage_key:    str
    is_enabled:   bool
    order_index:  int
    label:        Optional[str] = None
    timer_seconds: Optional[int] = 300   # таймер этапа в секундах (мин 1)


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
    current_user: User = Depends(get_current_user),
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
    # Новый набор активных stage_key (базовые, без ::N) — для проверки зависших устройств
    enabled_base_keys = {
        (s.stage_key.split('::')[0] if '::' in s.stage_key else s.stage_key)
        for s in body.stages if s.is_enabled
    }

    for s in body.stages:
        db.add(ProjectRouteStage(
            project_id=project_id,
            device_type=device_type,
            stage_key=s.stage_key,
            order_index=s.order_index,
            is_enabled=s.is_enabled,
            label=s.label or None,
            timer_seconds=max(1, s.timer_seconds or 300),
        ))

    # Автоматически переводим устройства, ожидающие удалённые этапы, записываем в историю
    advanced = _advance_stranded_devices(
        project_id, device_type, enabled_base_keys, db,
        worker_id=current_user.id,
    )

    db.commit()
    await ws_manager.broadcast({
        "type":         "project_route_saved",
        "project_id":   project_id,
        "project_name": project.name,
        "device_type":  device_type,
    })
    response = {
        "ok":      True,
        "message": "Маршрут проекта сохранён",
    }
    if advanced:
        response["advanced_devices"] = advanced
        response["advanced_count"]  = len(advanced)
        response["warning"] = (
            f"{len(advanced)} устройств автоматически переведены на следующий доступный этап"
        )
    return response


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
