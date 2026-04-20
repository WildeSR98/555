"""
API эндпоинты для Projects.
Полный функционал: Дерево (Проекты -> Устройства -> Операции), детали, создание проекта (с генерацией SN).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.database import get_db
from src.models import Project, Device, Operation, SerialNumber, DeviceModel, User, WorkLog, ProjectRoute, RouteConfig
from web.dependencies import get_current_user
from web.ws_manager import manager as ws_manager

router = APIRouter()


class DeviceRowInput(BaseModel):
    part_number: str
    model_id: int
    qty: int


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
    if status:
        query = query.filter(Project.status == status)
    
    # Используем selectinload для одного дополнительного запроса на каждый уровень вложенности вместо N+1
    projects = query.options(
        selectinload(Project.devices).selectinload(Device.operations)
    ).order_by(Project.created_at.desc()).all()
    
    tree = []
    for p in projects:
        p_node = {
            "id": p.id,
            "type": "project",
            "name": p.name,
            "code": p.code,
            "status": p.status,
            "status_display": p.status_display,
            "badge_color": Project.STATUS_COLORS.get(p.status, '#6c757d'),
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
        total = len(devices_list)
        
        done = sum(1 for d in devices_list if d.status in (['QC_PASSED', 'SHIPPED']))
        not_started = sum(1 for d in devices_list if d.status in (['PLANNING', 'WAITING_KITTING']))
        in_work = total - done - not_started
        
        return {
            "title": f"📁 Проект: {project.name}",
            "stats": {"total": total, "done": done, "not_started": not_started, "in_work": in_work},
            "fields": [
                {"label": "Код", "value": project.code},
                {"label": "Название", "value": project.name},
                {"label": "Статус", "value": project.status_display},
                {"label": "Спецификация", "value": project.spec_link or "—"},
                {"label": "Код подтверждения", "value": project.spec_code or "—"},
                {"label": "Менеджер", "value": project.manager.full_name if project.manager else "—"},
                {"label": "Создан", "value": project.created_at.strftime('%d.%m.%Y %H:%M') if project.created_at else "—"},
                {"label": "Устройств", "value": total},
            ]
        }
        
    elif entity_type == 'device':
        device = db.query(Device).get(entity_id)
        if not device:
            raise HTTPException(404, "Device not found")
            
        return {
            "title": f"💻 Устройство: {device.name}",
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
        
        current_counters = {}
        device_count = 0
        
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
                    
            for i in range(row.qty):
                device_count += 1
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
                
                new_sn_record = SerialNumber(
                    sn=new_sn_str,
                    model_id=dm.id,
                    is_used=True,
                    device_id=new_device.id,
                    created_at=datetime.now()
                )
                db.add(new_sn_record)
                
        db.commit()

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

        await ws_manager.broadcast({
            "type":        "project_created",
            "id":          new_proj.id,
            "name":        new_proj.name,
            "code":        new_proj.code or "",
            "device_count": device_count,
        })

        return {"ok": True, "message": f"Проект создан. Сгенерировано устройств: {device_count}"}
        
    except Exception as e:
        db.rollback()
        if 'UNIQUE constraint failed' in str(e):
            raise HTTPException(400, "Проект с таким кодом уже существует")
        raise HTTPException(500, str(e))


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

