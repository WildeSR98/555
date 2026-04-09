"""
API эндпоинты для Projects.
Полный функционал: Дерево (Проекты -> Устройства -> Операции), детали, создание проекта (с генерацией SN).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.database import get_db
from src.models import Project, Device, Operation, SerialNumber, DeviceModel

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
    devices: List[DeviceRowInput]


@router.get("/tree")
async def get_projects_tree(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Получить дерево проектов -> устройств -> операций."""
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    
    projects = query.order_by(Project.created_at.desc()).all()
    
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
        
        # Получаем устройства
        devices = db.query(Device).filter(Device.project_id == p.id).order_by(Device.name).all()
        for d in devices:
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
            
            # Получаем операции
            ops = db.query(Operation).filter(Operation.device_id == d.id).order_by(Operation.id).all()
            for op in ops:
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
async def get_entity_details(entity_type: str, entity_id: int, db: Session = Depends(get_db)):
    """Получить детали для панели справа."""
    if entity_type == 'project':
        project = db.query(Project).get(entity_id)
        if not project:
            raise HTTPException(404, "Project not found")
        
        # Считаем статистику
        total = project.devices.count()
        done = db.query(Device).filter(Device.project_id == entity_id, Device.status.in_(['QC_PASSED', 'SHIPPED'])).count()
        not_started = db.query(Device).filter(Device.project_id == entity_id, Device.status.in_(['PLANNING', 'WAITING_KITTING'])).count()
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
async def create_project(data: ProjectCreateRequest, db: Session = Depends(get_db)):
    """Создать проект с автоматической генерацией SN."""
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
                    status='PRE_PRODUCTION',
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
        return {"ok": True, "message": f"Проект создан. Сгенерировано устройств: {device_count}"}
        
    except Exception as e:
        db.rollback()
        if 'UNIQUE constraint failed' in str(e):
            raise HTTPException(400, "Проект с таким кодом уже существует")
        raise HTTPException(500, str(e))


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Удалить проект."""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
        
    # Связанные устройства, операции и SN удаляться cascade, 
    # если ORM настроен верно. В данной системе обычно просто db.delete()
    db.delete(project)
    db.commit()
    return {"ok": True, "message": "Проект удален"}
