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
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.database import get_db
from src.models import Workplace, WorkSession, WorkLog, Device, User, Project
from src.logic.workflow import WorkflowEngine

router = APIRouter()


class StartSessionRequest(BaseModel):
    workplace_id: int
    worker_code: str


class ProcessBatchRequest(BaseModel):
    session_id: int
    workplace_id: int
    worker_id: int
    serial_numbers: List[str]


class ActionRequest(BaseModel):
    session_id: int
    workplace_id: int
    worker_id: int
    device_ids: List[int]
    action: str  # complete, defect, keep, semifinished


class EndSessionRequest(BaseModel):
    session_id: int


@router.get("/workplaces")
async def get_workplaces(db: Session = Depends(get_db)):
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
async def start_session(data: StartSessionRequest, db: Session = Depends(get_db)):
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
async def process_batch(data: ProcessBatchRequest, db: Session = Depends(get_db)):
    """Шаг 2: Обработка пакета SN — валидация и приём в работу."""
    workplace = db.query(Workplace).get(data.workplace_id)
    if not workplace:
        raise HTTPException(404, 'Рабочее место не найдено')

    worker = db.query(User).get(data.worker_id)
    if not worker:
        raise HTTPException(404, 'Работник не найден')

    valid_devices = []
    to_scan_in = []
    already_in = []

    for sn in data.serial_numbers:
        device = db.query(Device).filter(Device.serial_number == sn).first()
        if not device:
            raise HTTPException(400, f'Устройство SN "{sn}" не найдено')

        if hasattr(device, 'is_semifinished') and device.is_semifinished:
            if hasattr(workplace, 'accepts_semifinished') and not workplace.accepts_semifinished:
                raise HTTPException(400, f'{sn}: Стенд не принимает полуфабрикаты')

        if hasattr(workplace, 'restrict_same_worker') and workplace.restrict_same_worker:
            last_log = db.query(WorkLog).filter(
                WorkLog.device_id == device.id,
                WorkLog.action == 'COMPLETED'
            ).order_by(WorkLog.created_at.desc()).first()
            if last_log and last_log.worker_id == data.worker_id:
                raise HTTPException(400, f'{sn}: Вы выполняли предыдущий этап. Запрет подряд.')

        valid_devices.append(device)

        # Определяем: нужно принять в работу или уже на этом этапе
        if device.status.startswith('WAITING_') or device.status != workplace.workplace_type:
            to_scan_in.append(device)
        else:
            already_in.append(device)

    # Если есть устройства для приёма в работу — делаем SCAN_IN
    scan_in_results = []
    if to_scan_in:
        for device in to_scan_in:
            old_status = device.status
            device.status = workplace.workplace_type
            device.current_worker_id = data.worker_id
            device.updated_at = datetime.now()

            log = WorkLog(
                worker_id=data.worker_id,
                session_id=data.session_id,
                workplace_id=data.workplace_id,
                device_id=device.id,
                project_id=device.project_id,
                action='SCAN_IN',
                old_status=old_status,
                new_status=device.status,
                part_number=device.part_number or '',
                serial_number=device.serial_number or '',
                created_at=datetime.now(),
            )
            db.add(log)
            scan_in_results.append({"sn": device.serial_number, "action": "SCAN_IN"})
        db.commit()

    return {
        "ok": True,
        "scan_in_count": len(to_scan_in),
        "already_in_count": len(already_in),
        "scan_in_results": scan_in_results,
        "device_ids": [d.id for d in valid_devices],
        "devices": [
            {"id": d.id, "sn": d.serial_number, "name": d.name, "status": d.status}
            for d in valid_devices
        ],
        "need_action": len(already_in) > 0,
    }


@router.post("/action")
async def do_action(data: ActionRequest, db: Session = Depends(get_db)):
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

    results = []
    for device_id in data.device_ids:
        device = db.query(Device).get(device_id)
        if not device:
            continue

        old_status = device.status

        if data.action == 'complete':
            new_status = STATUS_MAP.get(old_status, 'QC_PASSED')
            device.status = new_status
            device.current_worker_id = None
            action_type = 'COMPLETED'
        elif data.action == 'defect':
            device.status = 'DEFECT'
            device.current_worker_id = None
            action_type = 'DEFECT'
        elif data.action == 'keep':
            action_type = 'KEPT'
        elif data.action == 'semifinished':
            device.is_semifinished = True
            device.current_worker_id = None
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
        results.append({"sn": device.serial_number, "action": action_type})

    db.commit()

    ACTION_DISPLAYS = {
        'COMPLETED': '✅ Готово',
        'DEFECT': '⚠️ Брак',
        'KEPT': '📌 Оставлено',
        'MAKE_SEMIFINISHED': '🔧 Полуфабрикат',
    }

    return {
        "ok": True,
        "message": f'{ACTION_DISPLAYS.get(action_type, data.action)} — {len(results)} устр.',
        "results": results,
    }


@router.post("/end-session")
async def end_session(data: EndSessionRequest, db: Session = Depends(get_db)):
    """Завершить рабочую сессию."""
    ws = db.query(WorkSession).get(data.session_id)
    if ws:
        ws.is_active = False
        ws.ended_at = datetime.now()
        db.commit()
    return {"ok": True}
