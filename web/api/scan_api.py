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
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re

from src.database import get_db
from src.models import Workplace, WorkSession, WorkLog, Device, User, Project
from src.logic.workflow import WorkflowEngine
from web.dependencies import get_current_user

router = APIRouter()


class StartSessionRequest(BaseModel):
    workplace_id: int = Field(..., gt=0)
    worker_code: str = Field(..., min_length=2, max_length=50)

    @field_validator('worker_code')
    @classmethod
    def validate_worker_code(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('worker_code must be alphanumeric (plus _ or -)')
        return v


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
def start_session(data: StartSessionRequest, db: Session = Depends(get_db)):
    """Шаг 1: Выбрать рабочее место + отсканировать QR работника."""
    # Найти работника
    worker = db.query(User).filter(
        or_(User.username == data.worker_code, User.first_name == data.worker_code)
    ).first()
    
    if not worker:
        raise HTTPException(404, f'Работник "{data.worker_code}" не найден')

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

            # Проверка спецификации (спеки)
            if device.project and device.project.spec_link and device.project.spec_code:
                if device.project.id not in (data.verified_project_ids or []):
                    return {
                        "ok": False,
                        "require_spec": True,
                        "project_id": device.project.id,
                        "spec_link": device.project.spec_link,
                        "spec_code": device.project.spec_code
                    }

            # 1. Валидация по логике Workflow (можно ли принять этот SN на этот пост)
            ok, msg = WorkflowEngine.can_accept_device(workplace.workplace_type, device.status)
            if not ok:
                return {"ok": False, "error": f'{sn}: {msg}'}

            valid_devices.append(device)

            # Определяем: нужно принять в работу или уже принят
            status = device.status or ""
            if status.startswith('WAITING_') or status != workplace.workplace_type:
                to_scan_in.append(device)
            else:
                already_in.append(device)

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
def do_action(
    data: ActionRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Шаг 3: Действие с устройствами (Готово / Брак / Оставить / Полуфабрикат)."""
    STATUS_MAP = {
        'KITTING': 'WAITING_PRE_PRODUCTION',
        'PRE_PRODUCTION': 'WAITING_ASSEMBLY',
        'ASSEMBLY': 'WAITING_VIBROSTAND',
        'VIBROSTAND': 'WAITING_TECH_CONTROL_1_1',
        'TECH_CONTROL_1_1': 'WAITING_FUNC_CONTROL',
        'TECH_CONTROL_1_2': 'WAITING_FUNC_CONTROL',
        'FUNC_CONTROL': 'WAITING_TECH_CONTROL_2_1',
        'TECH_CONTROL_2_1': 'WAITING_PACKING',
        'TECH_CONTROL_2_2': 'WAITING_PACKING',
        'PACKING': 'WAITING_ACCOUNTING',
        'ACCOUNTING': 'WAREHOUSE',
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
                new_status = STATUS_MAP.get(old_status, 'QC_PASSED')
                
                # Проверка Workflow
                last_log = db.query(WorkLog).filter(WorkLog.device_id == device.id).order_by(WorkLog.created_at.desc()).first()
                ok, msg = WorkflowEngine.can_change_status(device, new_status, current_user, last_log)
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
                created_at=datetime.now(),
            )
            db.add(log)
            results.append({"sn": device.serial_number, "action": action_type, "device_id": device.id, "new_status": device.status})

        db.commit()

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
