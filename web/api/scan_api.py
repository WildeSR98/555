"""
API эндпоинты для Scan — производственный процесс сканирования.
Полный workflow как в десктопной scan_tab.py:
- Список рабочих мест
- Старт сессии (пост + работник)
- Обработка пакета SN
- Действие (complete/defect/keep/semifinished)
- Завершение сессии
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.database import get_db
from src.models import Workplace, WorkSession, WorkLog, Device, User, Project, ProjectRoute, ProjectRouteStage, RouteConfig
from src.logic.workflow import WorkflowEngine
from src.system_config import get_route_bypass_roles, get_cooldown_bypass_roles
from web.dependencies import get_current_user
from web.ws_manager import manager as ws_manager

router = APIRouter()


# ─── Логика пропуска отключённых этапов согласно маршруту проекта ──────────────────

_STAGE_NEXT = {
    # комплетед этап → следующий WAITING
    'PRE_PRODUCTION':    'WAITING_ASSEMBLY',
    'KITTING':           'WAITING_ASSEMBLY',
    'ASSEMBLY':          'WAITING_VIBROSTAND',
    'VIBROSTAND':        'WAITING_TECH_CONTROL_1_1',
    'TECH_CONTROL_1_1':  'WAITING_TECH_CONTROL_1_2',
    'TECH_CONTROL_1_2':  'WAITING_FUNC_CONTROL',
    'FUNC_CONTROL':      'WAITING_TECH_CONTROL_2_1',
    'TECH_CONTROL_2_1':  'WAITING_TECH_CONTROL_2_2',
    'TECH_CONTROL_2_2':  'WAITING_PACKING',
    'PACKING':           'WAITING_ACCOUNTING',
    'ACCOUNTING':        'WAITING_WAREHOUSE',
    'WAREHOUSE':         'QC_PASSED',
}


def resolve_next_status(current_status: str, enabled_stages: list) -> str:
    """
    Берёт следующий статус с учётом активных этапов маршрута.
    Если следующий этап отключён — пропускает его и ищет дальше.
    """
    if not enabled_stages:   # Дефолтный маршрут — все этапы активны
        return _STAGE_NEXT.get(current_status, 'QC_PASSED')

    candidate = _STAGE_NEXT.get(current_status, 'QC_PASSED')
    for _ in range(15):  # защита от бесконечного цикла
        if not candidate or not candidate.startswith('WAITING_'):
            return candidate  # QC_PASSED или терминальный статус
        stage = candidate[len('WAITING_'):]  # WAITING_VIBROSTAND → VIBROSTAND
        if stage in enabled_stages:
            return candidate  # этап активен
        # Этап отключён — пропускаем: находим что идёт после этого этапа
        candidate = _STAGE_NEXT.get(stage, 'QC_PASSED')
    return candidate


class StartSessionRequest(BaseModel):
    workplace_id: int = Field(..., gt=0)


class ProcessBatchRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    workplace_id: int = Field(..., gt=0)
    worker_id: int = Field(..., gt=0)
    serial_numbers: List[str] = Field(..., min_length=1, max_length=100)
    verified_project_ids: Optional[List[int]] = []


class ActionRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    workplace_id: int = Field(..., gt=0)
    worker_id: int = Field(..., gt=0)
    device_ids: List[int] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern='^(complete|defect|keep|semifinished|scan_in)$')
    notes: Optional[str] = ''
    target_status: Optional[str] = None  # Явный целевой статус (для поста Ремонта)


class EndSessionRequest(BaseModel):
    session_id: int = Field(..., gt=0)


@router.get("/workplaces")
def get_workplaces(db: Session = Depends(get_db)):
    """Список активных рабочих мест."""
    workplaces = db.query(Workplace).filter(
        Workplace.is_active == True
    ).order_by(Workplace.order).all()
    
    return [
        {
            "id": wp.id,
            "name": wp.name,
            "type": wp.type_display,
            "workplace_type": wp.workplace_type,
        }
        for wp in workplaces
    ]


@router.post("/start-session")
def start_session(
    data: StartSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Шаг 1: Выбрать рабочее место. Работник — текущий авторизованный пользователь сайта."""
    worker = current_user

    workplace = db.query(Workplace).get(data.workplace_id)
    if not workplace:
        raise HTTPException(404, 'Рабочее место не найдено')

    # Проверить наличие активной сессии
    active = db.query(WorkSession).filter(
        WorkSession.worker_id == worker.id,
        WorkSession.workplace_id == workplace.id,
        WorkSession.is_active == True
    ).first()

    if active:
        session_obj = active
    else:
        session_obj = WorkSession(
            worker_id=worker.id,
            workplace_id=workplace.id,
            started_at=datetime.now(),
            is_active=True,
        )
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)

    return {
        "ok": True,
        "session_id": session_obj.id,
        "worker_id": worker.id,
        "worker_name": worker.full_name,
        "workplace_name": workplace.name,
        "workplace_type": workplace.workplace_type,
        "batch_limit": WorkflowEngine.get_batch_limit(workplace.workplace_type),
    }


@router.post("/process-batch")
def process_batch(
    data: ProcessBatchRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Шаг 2: Обработка пакета SN — валидация и приём в работу."""
    try:
        workplace = db.query(Workplace).get(data.workplace_id)
        if not workplace:
            raise HTTPException(404, 'Рабочее место не найдено')

        worker = db.query(User).get(data.worker_id)
        if not worker:
            raise HTTPException(404, 'Работник не найден')

        valid_devices = []
        to_scan_in = []
        already_in = []

        from sqlalchemy.orm import joinedload
        for sn in data.serial_numbers:
            # Оптимизация: загружаем проект и спеку сразу
            device = db.query(Device).options(joinedload(Device.project)).filter(Device.serial_number == sn).first()
            if not device:
                return {
                    "ok": False,
                    "error": f'Устройство SN "{sn}" не найдено'
                }

            if hasattr(device, 'is_semifinished') and device.is_semifinished:
                if hasattr(workplace, 'accepts_semifinished') and not workplace.accepts_semifinished:
                    return {
                        "ok": False,
                        "error": f'{sn}: Стенд не принимает полуфабрикаты'
                    }

            if hasattr(workplace, 'restrict_same_worker') and workplace.restrict_same_worker:
                last_log = db.query(WorkLog).filter(
                    WorkLog.device_id == device.id,
                    WorkLog.action == 'COMPLETED'
                ).order_by(WorkLog.created_at.desc()).first()
                if last_log and last_log.worker_id == data.worker_id:
                    return {
                        "ok": False,
                        "error": f'{sn}: Вы выполняли предыдущий этап. Запрет подряд.'
                    }

            # Определяем заранее: уже принято в работу или ещё нет
            already_accepted = (device.status == workplace.workplace_type)

            # Проверка спецификации — обязательна для ВСЕХ (включая admin/начальника цеха)
            if not already_accepted and device.project and device.project.spec_link and device.project.spec_code:
                if device.project.id not in (data.verified_project_ids or []):
                    return {
                        "ok": False,
                        "require_spec": True,
                        "project_id": device.project.id,
                        "spec_link": device.project.spec_link,
                        "spec_code": device.project.spec_code
                    }

            # Проверка маршрута — только для обычных пользователей.
            # Привилегированные роли читаются из БД (root настраивает через админпанель).
            route_bypass = get_route_bypass_roles(db)
            is_privileged = current_user.role in route_bypass
            if not is_privileged:
                ok, msg = WorkflowEngine.can_accept_device(workplace.workplace_type, device.status)
                if not ok:
                    return {"ok": False, "error": f'{sn}: {msg}'}

            valid_devices.append(device)

            # Определяем: нужно принять в работу или уже принят
            if already_accepted:
                already_in.append(device)
            else:
                to_scan_in.append(device)

        # process-batch только ВАЛИДИРУЕТ. SCAN_IN делается отдельным шагом через action=scan_in.
        return {
            "ok": True,
            "need_scan_in": len(to_scan_in) > 0,
            "already_in_count": len(already_in),
            "device_ids": [d.id for d in valid_devices],
            "devices": [
                {"id": d.id, "sn": d.serial_number, "name": d.name, "status": d.status,
                 "need_scan_in": d in to_scan_in}
                for d in valid_devices
            ],
            "need_action": len(valid_devices) > 0,
        }
    except Exception as e:
        # Ловим все ошибки и отдаем как 400 чтобы фронт показал текст ошибки
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/action")
async def do_action(
    data: ActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Шаг 3: Действие с устройствами (Готово / Брак / Оставить / Полуфабрикат)."""
    STATUS_MAP = {
        'PRE_PRODUCTION': 'WAITING_ASSEMBLY',  # Комплектовка → Сборка
        'KITTING': 'WAITING_ASSEMBLY',
        'ASSEMBLY': 'WAITING_VIBROSTAND',
        'VIBROSTAND': 'WAITING_TECH_CONTROL_1_1',
        'TECH_CONTROL_1_1': 'WAITING_TECH_CONTROL_1_2',
        'TECH_CONTROL_1_2': 'WAITING_FUNC_CONTROL',
        'FUNC_CONTROL': 'WAITING_TECH_CONTROL_2_1',
        'TECH_CONTROL_2_1': 'WAITING_TECH_CONTROL_2_2',
        'TECH_CONTROL_2_2': 'WAITING_PACKING',
        'PACKING': 'WAITING_ACCOUNTING',
        'ACCOUNTING': 'WAITING_WAREHOUSE',
        'WAREHOUSE': 'QC_PASSED',
    }

    try:
        results = []
        action_type = data.action

        for device_id in data.device_ids:
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                continue

            old_status = device.status

            if data.action == 'scan_in':
                # Явный SCAN_IN: принять устройство в работу на этом посту
                workplace = db.query(Workplace).get(data.workplace_id)
                device.status = workplace.workplace_type
                device.current_worker_id = data.worker_id
                device.updated_at = datetime.now()
                action_type = 'SCAN_IN'
            elif data.action == 'complete':
                # Если передан явный target_status (пост Ремонта выбирает куда отправить)
                if data.target_status:
                    ALLOWED_REPAIR_TARGETS = [
                        'WAITING_KITTING',
                        'WAITING_ASSEMBLY', 'WAITING_VIBROSTAND',
                        'WAITING_TECH_CONTROL_1_1', 'WAITING_TECH_CONTROL_1_2',
                        'WAITING_FUNC_CONTROL',
                    ]
                    if data.target_status not in ALLOWED_REPAIR_TARGETS:
                        return {"ok": False, "error": f"{device.serial_number}: Недопустимый целевой статус после ремонта."}
                    new_status = data.target_status
                else:
                    # Получаем активные этапы из проектного маршрута (ProjectRouteStage),
                    # если нет — из глобального RouteConfig
                    overrides = (
                        db.query(ProjectRouteStage)
                        .filter_by(project_id=device.project_id, device_type=device.device_type)
                        .order_by(ProjectRouteStage.order_index)
                        .all()
                    )
                    if overrides:
                        enabled = [
                            (s.stage_key.split('::')[0] if '::' in s.stage_key else s.stage_key)
                            for s in overrides if s.is_enabled
                        ]
                    else:
                        rc = (
                            db.query(RouteConfig).filter_by(device_type=device.device_type).first()
                            or db.query(RouteConfig).filter_by(is_default=True).first()
                        )
                        enabled = rc.get_enabled_stages() if rc else []
                    new_status = resolve_next_status(old_status, enabled)
                
                # Проверка Workflow
                last_log = db.query(WorkLog).filter(WorkLog.device_id == device.id).order_by(WorkLog.created_at.desc()).first()
                ok, msg = WorkflowEngine.can_change_status(
                    device, new_status, current_user, last_log,
                    cooldown_bypass_roles=get_cooldown_bypass_roles(db)
                )
                if not ok:
                    return {"ok": False, "error": f"{device.serial_number}: {msg}"}

                device.status = new_status
                device.current_worker_id = None
                device.updated_at = datetime.now()
                action_type = 'COMPLETED'
            elif data.action == 'defect':
                device.status = 'DEFECT'
                device.current_worker_id = None
                device.updated_at = datetime.now()
                action_type = 'DEFECT'
            elif data.action == 'semifinished':
                device.is_semifinished = True
                device.current_worker_id = None
                device.updated_at = datetime.now()
                action_type = 'MAKE_SEMIFINISHED'
            else:
                continue

            # Действия ROOT не сохраняются в WorkLog
            if current_user.role != User.ROLE_ROOT:
                log = WorkLog(
                    worker_id=data.worker_id,
                    session_id=data.session_id,
                    workplace_id=data.workplace_id,
                    device_id=device.id,
                    project_id=device.project_id,
                    action=action_type,
                    old_status=old_status,
                    new_status=device.status,
                    part_number=device.part_number or '',
                    serial_number=device.serial_number or '',
                    notes=data.notes or '',
                    created_at=datetime.now(),
                )
                db.add(log)
            results.append({"sn": device.serial_number, "action": action_type, "device_id": device.id, "new_status": device.status, "old_status": old_status})

        db.commit()

        # ─── WebSocket broadcast ───
        for r in results:
            dev = db.query(Device).filter(Device.id == r['device_id']).first()
            if dev:
                await ws_manager.broadcast({
                    "type":               "device_status_changed",
                    "device_id":          dev.id,
                    "device_name":        dev.name,
                    "serial_number":      dev.serial_number or "",
                    "project_id":         dev.project_id,
                    "project_name":       dev.project.name if dev.project else "",
                    "old_status":         r.get("old_status", ""),
                    "new_status":         dev.status,
                    "old_status_display": Device.STATUS_DISPLAY.get(r.get("old_status", ""), r.get("old_status", "")),
                    "new_status_display": Device.STATUS_DISPLAY.get(dev.status, dev.status),
                    "action":             r["action"],
                    "worker":             current_user.full_name or current_user.username,
                    "timestamp":          datetime.now().strftime('%d.%m.%Y %H:%M'),
                })

        ACTION_DISPLAYS = {
            'COMPLETED': '✅ Готово',
            'DEFECT': '⚠️ Брак',
            'KEPT': '📌 Оставлено',
            'MAKE_SEMIFINISHED': '🔧 Полуфабрикат',
            'SCAN_IN': '📥 Принят'
        }

        return {
            "ok": True,
            "message": f'{ACTION_DISPLAYS.get(action_type, data.action)} — {len(results)} устр.',
            "results": results,
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[do_action ERROR] {tb}")
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {str(e)}")


@router.post("/end-session")
def end_session(data: EndSessionRequest, db: Session = Depends(get_db)):
    """Завершить рабочую сессию."""
    ws = db.query(WorkSession).get(data.session_id)
    if ws:
        ws.is_active = False
        ws.ended_at = datetime.now()
        db.commit()
    return {"ok": True}
