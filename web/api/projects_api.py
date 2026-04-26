"""
API эндпоинты для Projects.
Полный функционал: Дерево (Проекты -> Устройства -> Операции), детали, создание проекта (с генерацией SN).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

from src.database import get_db
from src.models import (
    Project, Device, Operation, SerialNumber, DeviceModel, User,
    WorkLog, ProjectRoute, RouteConfig,
    MacAddress, DUAL_MAC_CATEGORIES, SINGLE_MAC_CATEGORIES,
)
from web.dependencies import get_current_user
from web.ws_manager import manager as ws_manager

router = APIRouter()


# ── Pipeline position helpers ─────────────────────────────────────────────────

# Position 0 = start of kitting; 11 = done (QC_PASSED/SHIPPED)
# done_at_stage_N = devices with pos > N
_STATUS_PIPELINE_POS: dict[str, int] = {
    'WAITING_KITTING': 0, 'WAITING_PRE_PRODUCTION': 0, 'PRE_PRODUCTION': 0,
    'WAITING_ASSEMBLY': 1, 'ASSEMBLY': 1,
    'WAITING_VIBROSTAND': 2, 'VIBROSTAND': 2,
    'WAITING_TECH_CONTROL_1_1': 3, 'TECH_CONTROL_1_1': 3,
    'WAITING_TECH_CONTROL_1_2': 4, 'TECH_CONTROL_1_2': 4,
    'WAITING_FUNC_CONTROL': 5, 'FUNC_CONTROL': 5,
    'WAITING_TECH_CONTROL_2_1': 6, 'TECH_CONTROL_2_1': 6,
    'WAITING_TECH_CONTROL_2_2': 7, 'TECH_CONTROL_2_2': 7,
    'WAITING_PACKING': 8, 'PACKING': 8,
    'WAITING_ACCOUNTING': 9, 'ACCOUNTING': 9,
    'WAITING_WAREHOUSE': 10, 'WAREHOUSE': 10,
    'QC_PASSED': 11, 'SHIPPED': 11,
}
_STAGE_DEFS = [
    (0, 'Компл.'), (1, 'Сборка'), (2, 'Вибро'),
    (3, 'ОТК1.1'),   (4, 'ОТК1.2'), (5, 'Функц.'),
    (6, 'ОТК2.1'),   (7, 'ОТК2.2'), (8, 'Упак.'),
    (9, 'Учёт'),     (10, 'Склад'),
]


def _compute_project_stats(devices: list) -> dict:
    """Вычисляет completion_pct, stage_stats, total, total_done."""
    total = len(devices)
    if total == 0:
        return {'total': 0, 'total_done': 0, 'completion_pct': 0, 'stage_stats': []}
    positions = [_STATUS_PIPELINE_POS.get(d.status, 0) for d in devices]
    max_pos = max(positions)
    total_done = sum(1 for p in positions if p >= 11)
    completion_pct = round(total_done / total * 100)
    stage_stats = [
        {'idx': idx, 'short': short,
         'done': sum(1 for pos in positions if pos > idx),
         'total': total}
        for idx, short in _STAGE_DEFS
        if idx <= max_pos  # показываем только те этапы, которых достиг хоть один устрой
    ]
    return {
        'total': total,
        'total_done': total_done,
        'completion_pct': completion_pct,
        'stage_stats': stage_stats,
    }


# ── MAC helpers ───────────────────────────────────────────────────────────────

import re as _re


def _norm_mac(raw: str) -> str | None:
    """Нормализует MAC-адрес: убирает разделители, приводит к XX:XX:XX:XX:XX:XX."""
    d = _re.sub(r'[^0-9a-fA-F]', '', raw.strip())
    return ':'.join(d[j:j+2].upper() for j in range(0, 12, 2)) if len(d) == 12 else None


def _mac_to_int(mac: str) -> int:
    return int(mac.replace(':', ''), 16)


def _int_to_mac(n: int) -> str:
    h = f'{n:012X}'
    return ':'.join(h[i:i+2] for i in range(0, 12, 2))


def _next_free_mac(db: Session, device_id: int, project_id: int = None) -> str:
    """
    Берёт следующий свободный MAC из пула (если есть),
    иначе генерирует новый = последний MAC в БД + 1.
    Raises ValueError если пул полностью пуст (нет якоря).
    """
    # 1. Попытка взять из свободных
    rec = db.query(MacAddress).filter_by(is_used=False).order_by(MacAddress.id).first()
    if rec:
        rec.is_used    = True
        rec.device_id  = device_id
        rec.project_id = project_id
        return rec.mac

    # 2. Генерация: якорь = последний MAC в БД (по id desc)
    last = db.query(MacAddress).order_by(MacAddress.id.desc()).first()
    if last is None:
        raise ValueError('MAC-пул пуст. Добавьте хотя бы один MAC вручную как якорь.')

    new_mac = _int_to_mac(_mac_to_int(last.mac) + 1)
    # Коллизия (крайне маловероятна)
    while db.query(MacAddress).filter_by(mac=new_mac).first():
        new_mac = _int_to_mac(_mac_to_int(new_mac) + 1)

    db.add(MacAddress(mac=new_mac, mac_type='LAN', is_used=True,
                      device_id=device_id, project_id=project_id, created_at=datetime.now()))
    db.flush()
    return new_mac


def _assign_manual_mac(db: Session, raw: str, device_id: int, project_id: int = None) -> str | None:
    """Назначает вручную введённый MAC (создаёт запись в пуле если нет)."""
    mac_val = _norm_mac(raw) if raw else None
    if not mac_val:
        return None
    existing = db.query(MacAddress).filter_by(mac=mac_val).first()
    if not existing:
        db.add(MacAddress(mac=mac_val, mac_type='LAN', is_used=True,
                          device_id=device_id, project_id=project_id, created_at=datetime.now()))
    elif not existing.is_used:
        existing.is_used    = True
        existing.device_id  = device_id
        existing.project_id = project_id
    elif existing.device_id != device_id:
        raise ValueError(f"MAC {mac_val} уже используется устройством #{existing.device_id}")
    return mac_val


class ManualMacEntry(BaseModel):
    mac1: str = ''   # LAN
    mac2: str = ''   # BMC (только для TIOGA/SERVAL/OCTOPUS)


class DeviceRowInput(BaseModel):
    part_number: str
    model_id: int
    qty: int
    sn_mode: str = 'pool'               # 'pool' | 'manual'
    manual_sns: List[str] = []          # при sn_mode='manual', len == qty
    mac_mode: str = 'pool'              # 'pool' | 'manual'
    manual_macs: List[ManualMacEntry] = []   # при mac_mode='manual', len == qty


class ProjectCreateRequest(BaseModel):
    code: Optional[str] = None
    name: str
    spec_link: Optional[str] = None
    spec_code: Optional[str] = None
    manager_id: Optional[int] = None
    route_config_id: Optional[int] = None   # Маршрутный лист
    devices: List[DeviceRowInput]


class DeleteProjectRequest(BaseModel):
    password: str


@router.get("/tree")
def get_projects_tree(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Получить дерево проектов -> устройств -> операций (Оптимизировано)."""
    query = db.query(Project)
    if status == 'ARCHIVED':
        # Вкладка Архив — показываем только архивные
        query = query.filter(Project.status == 'ARCHIVED')
    elif status:
        # Конкретный статус (не ARCHIVED) — фильтруем
        query = query.filter(Project.status == status)
    else:
        # По умолчанию — скрываем архивные (они на отдельной вкладке)
        query = query.filter(Project.status != 'ARCHIVED')
    
    # Используем selectinload для одного дополнительного запроса на каждый уровень вложенности вместо N+1
    projects = query.options(
        selectinload(Project.devices).selectinload(Device.operations)
    ).order_by(Project.created_at.desc()).all()
    
    tree = []
    for p in projects:
        ps = _compute_project_stats(p.devices)
        p_node = {
            "id": p.id,
            "type": "project",
            "name": p.name,
            "code": p.code,
            "status": p.status,
            "status_display": p.status_display,
            "badge_color": Project.STATUS_COLORS.get(p.status, '#6c757d'),
            "completion_pct": ps['completion_pct'],
            "total": ps['total'],
            "total_done": ps['total_done'],
            "stage_stats": ps['stage_stats'],
            "children": []
        }
        
        for d in p.devices:
            d_node = {
                "id": d.id,
                "type": "device",
                "name": d.name,
                "code": d.code,
                "status": d.status,
                "status_display": d.status_display,
                "badge_color": Device.STATUS_COLORS.get(d.status, '#6c757d'),
                "sn_pn": f"SN: {d.serial_number}" if d.serial_number else f"PN: {d.part_number}",
                "children": []
            }
            
            for op in d.operations:
                op_node = {
                    "id": op.id,
                    "type": "operation",
                    "name": op.title,
                    "code": op.code,
                    "status": op.status,
                    "status_display": op.status_display,
                    "badge_color": Operation.STATUS_COLORS.get(op.status, '#6c757d'),
                }
                d_node["children"].append(op_node)
            
            p_node["children"].append(d_node)
            
        tree.append(p_node)
        
    return tree


@router.get("/{entity_type}/{entity_id}")
def get_entity_details(entity_type: str, entity_id: int, db: Session = Depends(get_db)):
    """Получить детали для панели справа."""
    if entity_type == 'project':
        project = db.query(Project).get(entity_id)
        if not project:
            raise HTTPException(404, "Project not found")
        
        # Считаем статистику (теперь через len(project.devices), так как это список)
        devices_list = project.devices
        ps = _compute_project_stats(devices_list)
        # Сетевая папка
        import os as _os
        from pathlib import Path as _P
        net_base = _os.environ.get('NET_PROJECTS_DIR', '')
        if net_base:
            if project.status == 'ARCHIVED':
                net_path = str(_P(net_base) / 'Archive' / project.name)
            else:
                net_path = str(_P(net_base) / project.name)
        else:
            net_path = '—'

        return {
            "title": f"📁 Проект: {project.name}",
            "stats": {
                "total":          ps['total'],
                "done":           ps['total_done'],
                "not_started":    sum(1 for d in devices_list if d.status in ('PLANNING', 'WAITING_KITTING')),
                "in_work":        ps['total'] - ps['total_done'],
                "completion_pct": ps['completion_pct'],
                "stage_stats":    ps['stage_stats'],
            },
            "fields": [
                {"label": "Код",            "value": project.code},
                {"label": "Название",       "value": project.name},
                {"label": "Статус",         "value": project.status_display},
                {"label": "Спецификация",   "value": project.spec_link or "—"},
                {"label": "Код подтверждения", "value": project.spec_code or "—"},
                {"label": "Менеджер",       "value": project.manager.full_name if project.manager else "—"},
                {"label": "Создан",         "value": project.created_at.strftime('%d.%m.%Y %H:%M') if project.created_at else "—"},
                {"label": "Устройств",      "value": ps['total']},
                {"label": "📂 Сетевая папка", "value": net_path},
            ]
        }
        
    elif entity_type == 'device':
        device = db.query(Device).get(entity_id)
        if not device:
            raise HTTPException(404, "Device not found")
            
        return {
            "title": f"💻 Устройство: {device.name}",
            "serial_number": device.serial_number,  # для кнопки «Перейти к сканированию»
            "fields": [
                {"label": "Код", "value": device.code or "—"},
                {"label": "Название", "value": device.name},
                {"label": "Серийный номер", "value": device.serial_number or "—"},
                {"label": "Партномер", "value": device.part_number or "—"},
                {"label": "Тип", "value": device.device_type_display},
                {"label": "Статус", "value": device.status_display},
                {"label": "Полуфабрикат", "value": "Да" if getattr(device, 'is_semifinished', False) else "Нет"},
                {"label": "Текущий работник", "value": device.current_worker.full_name if device.current_worker else "—"},
                {"label": "Расположение", "value": device.location or "—"},
            ]
        }
        
    elif entity_type == 'operation':
        op = db.query(Operation).get(entity_id)
        if not op:
            raise HTTPException(404, "Operation not found")
            
        return {
            "title": f"⚙ Операция: {op.title}",
            "fields": [
                {"label": "Код", "value": op.code or "—"},
                {"label": "Название", "value": op.title},
                {"label": "Статус", "value": op.status_display},
                {"label": "Создана", "value": op.created_at.strftime('%d.%m.%Y %H:%M') if op.created_at else "—"},
            ]
        }
        
    raise HTTPException(400, "Unknown entity type")


@router.post("/")
async def create_project(
    data: ProjectCreateRequest, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Создать проект с автоматической генерацией SN."""
    if user.role not in (User.ROLE_ADMIN, User.ROLE_MANAGER, User.ROLE_SHOP_MANAGER):
        raise HTTPException(403, "У вас недостаточно прав для создания проекта")
    if not data.name:
        raise HTTPException(400, "Название проекта не может быть пустым")
        
    try:
        new_proj = Project(
            name=data.name,
            code=data.code if data.code else None,
            spec_link=data.spec_link if data.spec_link else None,
            spec_code=data.spec_code if data.spec_code else None,
            status='PLANNING',
            manager_id=data.manager_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_proj)
        db.flush()
        
        device_count = 0
        current_counters: dict[str, int] = {}    # SN счётчики по префиксу
        all_devices_for_excel: list[dict] = []   # для генерации Excel
        mac_warnings: list[str] = []             # предупреждения о нехватке MAC

        for row in data.devices:
            if not row.part_number or not row.model_id or row.qty < 1:
                continue

            dm = db.query(DeviceModel).get(row.model_id)
            if not dm:
                continue

            prefix = dm.sn_prefix
            if prefix not in current_counters:
                last_sn = db.query(SerialNumber).filter(
                    SerialNumber.model_id == dm.id
                ).order_by(desc(SerialNumber.sn)).first()

                if last_sn:
                    num_str = last_sn.sn[len(prefix):]
                    try:
                        current_counters[prefix] = int(num_str)
                    except ValueError:
                        current_counters[prefix] = 0
                else:
                    current_counters[prefix] = 0

            # Определяем нужны ли MAC для данной категории
            cat = dm.category
            needs_mac1 = cat in DUAL_MAC_CATEGORIES or cat in SINGLE_MAC_CATEGORIES
            needs_mac2 = cat in DUAL_MAC_CATEGORIES

            for i in range(row.qty):
                device_count += 1

                # ── Определение SN ──────────────────────────────────────────
                if row.sn_mode == 'manual' and i < len(row.manual_sns):
                    new_sn_str = row.manual_sns[i].strip()
                    if not new_sn_str:
                        new_sn_str = f"{prefix}{(current_counters.get(prefix,0)+1):05d}"
                else:
                    current_counters[prefix] += 1
                    new_sn_str = f"{prefix}{current_counters[prefix]:05d}"

                new_device = Device(
                    project_id=new_proj.id,
                    name=f"{row.part_number} #{i+1}",
                    part_number=row.part_number,
                    device_type=dm.category,
                    serial_number=new_sn_str,
                    status='WAITING_KITTING',
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(new_device)
                db.flush()

                # SN запись в пул (always, даже для ручных)
                if not db.query(SerialNumber).filter_by(sn=new_sn_str).first():
                    db.add(SerialNumber(
                        sn=new_sn_str,
                        model_id=dm.id,
                        is_used=True,
                        device_id=new_device.id,
                        created_at=datetime.now()
                    ))

                # ── Назначение MAC-адресов ──────────────────────────────────
                mac1_val = mac2_val = None

                if needs_mac1:
                    if row.mac_mode == 'manual' and i < len(row.manual_macs):
                        mac1_val = _assign_manual_mac(db, row.manual_macs[i].mac1, new_device.id, project_id=new_proj.id)
                    else:
                        try:
                            mac1_val = _next_free_mac(db, new_device.id, project_id=new_proj.id)
                        except ValueError as e:
                            mac_warnings.append(str(e))

                if needs_mac2:
                    if row.mac_mode == 'manual' and i < len(row.manual_macs):
                        mac2_val = _assign_manual_mac(db, row.manual_macs[i].mac2, new_device.id, project_id=new_proj.id)
                    else:
                        try:
                            mac2_val = _next_free_mac(db, new_device.id, project_id=new_proj.id)
                        except ValueError as e:
                            mac_warnings.append(str(e))

                # Собираем данные для Excel (только устройства с MAC)
                if needs_mac1:
                    all_devices_for_excel.append({
                        'part_number':   row.part_number,
                        'serial_number': new_sn_str,
                        'mac1':          mac1_val or '',
                        'mac2':          mac2_val or '',
                        'category':      cat,
                    })

        db.commit()  # ── сохраняем устройства + MAC-привязки

        # Назначить маршрут
        route_id = data.route_config_id
        if not route_id:
            # Автовыбор: находим по типу устройства из первого рова
            if data.devices:
                first_dm = db.query(DeviceModel).get(data.devices[0].model_id)
                if first_dm:
                    rc = db.query(RouteConfig).filter_by(device_type=first_dm.category).first()
                    if rc:
                        route_id = rc.id
        if not route_id:
            rc_def = db.query(RouteConfig).filter_by(is_default=True).first()
            if rc_def:
                route_id = rc_def.id
        if route_id:
            db.add(ProjectRoute(
                project_id=new_proj.id,
                route_config_id=route_id,
                assigned_at=datetime.now(),
                assigned_by_id=user.id,
            ))
            db.commit()

        # ── Создать структуру папок на сетевом диске ─────────────────────────
        import logging as _netlog
        _netlog = _netlog.getLogger(__name__)
        folder_result: dict = {'ok': False, 'created': 0, 'error': 'not attempted'}
        try:
            import importlib.util as _ilu
            from pathlib import Path as _Path
            _script = _Path(__file__).resolve().parent.parent.parent / 'scripts' / 'create_project_folders.py'
            _spec = _ilu.spec_from_file_location('create_project_folders', _script)
            _mod  = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)

            folder_result = _mod.create_project_folders(
                project_name=new_proj.name,
                devices=[
                    {'part_number': d.part_number, 'serial_number': d.serial_number}
                    for d in new_proj.devices
                ],
            )
            if folder_result['ok']:
                _netlog.info(f'[NET] Папки созданы: {folder_result["created"]} шт. → {folder_result["path"]}')
            else:
                _netlog.warning(f'[NET] Папки не созданы: {folder_result.get("error")}')

            # ── Создать Excel-файл с MAC/SN ────────────────────────────────
            if all_devices_for_excel and folder_result.get('ok'):
                try:
                    excel_result = _mod.create_project_excel(
                        project_name=new_proj.name,
                        devices=all_devices_for_excel,
                    )
                    if excel_result.get('ok'):
                        _netlog.info(f'[NET] Excel создан: {excel_result["path"]}')
                except Exception as _xe:
                    _netlog.warning(f'[NET] Excel не создан: {_xe}')

        except Exception as _e:
            _netlog.warning(f'[NET] Ошибка при создании папок: {_e}', exc_info=True)
        # ── (ошибка сети не блокирует создание проекта) ───────────────────────


        await ws_manager.broadcast({
            "type":        "project_created",
            "id":          new_proj.id,
            "name":        new_proj.name,
            "code":        new_proj.code or "",
            "device_count": device_count,
        })

        net_msg = (
            f"Папки на сетевом диске созданы ({folder_result.get('created', 0)} шт.)"
            if folder_result.get('ok')
            else "Папки на сетевом диске не созданы (проверьте подключение)"
        )
        return {
            "ok": True,
            "message": f"Проект создан. Сгенерировано устройств: {device_count}",
            "net_folders": folder_result,
            "net_message": net_msg,
            "mac_warnings": mac_warnings,
        }
        
    except Exception as e:
        db.rollback()
        err_str = str(e)
        # PostgreSQL: "duplicate key value violates unique constraint"
        # SQLite:     "UNIQUE constraint failed"
        if 'duplicate key value' in err_str or 'UNIQUE constraint failed' in err_str:
            # Определяем по какому полю конфликт
            if 'code' in err_str:
                raise HTTPException(400, f'Проект с кодом "{data.code}" уже существует. Используйте другой код.')
            raise HTTPException(400, 'Проект с таким кодом уже существует')
        raise HTTPException(500, err_str)


@router.post("/{project_id}/delete")
async def delete_project(
    project_id: int, 
    data: DeleteProjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Удалить проект с проверкой пароля администратора."""
    if user.role not in (User.ROLE_ADMIN, User.ROLE_SHOP_MANAGER):
        raise HTTPException(403, "Только администратор или начальник цеха могут удалять проекты")
        
    if not user.check_password(data.password):
        raise HTTPException(401, "Неверный пароль администратора")

    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    try:
        # Manually delete all worklogs for devices in this project before deleting project
        db.query(WorkLog).filter(WorkLog.project_id == project_id).delete(synchronize_session=False)
        
        # Clear device ID references in serial numbers so they aren't deleted/failed on cascade
        db.execute(SerialNumber.__table__.update().where(
            SerialNumber.device_id.in_(
                [d.id for d in project.devices]
            )
        ).values(device_id=None, is_used=False))
        
        proj_name = project.name
        db.delete(project)
        db.commit()
        await ws_manager.broadcast({
            "type": "project_deleted",
            "id":   project_id,
            "name": proj_name,
        })
        return {"ok": True, "message": "Проект успешно удален"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

