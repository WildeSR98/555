"""
API эндпоинты для управления Пулом серийных номеров.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List
from datetime import datetime

from src.database import get_db
from src.models import Device, DeviceModel, SerialNumber

router = APIRouter()

class ModelCreateInput(BaseModel):
    category: str
    name: str
    sn_prefix: str

class CounterSetInput(BaseModel):
    count: int

@router.get("/tree")
async def get_sn_tree(db: Session = Depends(get_db)):
    """Получить дерево Категория -> Модель."""
    models = db.query(DeviceModel).order_by(DeviceModel.category, DeviceModel.name).all()
    
    cats = {}
    for k, v in Device.DEVICE_TYPE_DISPLAY.items():
        if k in Device.SN_PREFIXES:
            cats[k] = {
                "id": k,
                "name": v,
                "models": []
            }
            
    for m in models:
        if m.category in cats:
            cats[m.category]["models"].append({
                "id": m.id,
                "name": m.name,
                "prefix": m.sn_prefix
            })
            
    return list(cats.values())


@router.get("/categories")
async def get_categories():
    """Словарь категорий для формы."""
    res = []
    for k, v in Device.DEVICE_TYPE_DISPLAY.items():
        if k in Device.SN_PREFIXES:
            res.append({
                "id": k, "name": v, "prefix": Device.SN_PREFIXES[k]
            })
    return res


@router.get("/models/{model_id}/sns")
async def get_model_sns(model_id: int, sn: str = "", db: Session = Depends(get_db)):
    """Получить все SN для конкретной модели (с поиском)."""
    query = db.query(SerialNumber).filter(SerialNumber.model_id == model_id)
    if sn:
        query = query.filter(SerialNumber.sn.contains(sn))
        
    sns = query.order_by(SerialNumber.id.desc()).limit(500).all()
    
    return [
        {
            "id": s.id,
            "sn": s.sn,
            "is_used": s.is_used,
            "created_at": s.created_at.strftime('%d.%m.%Y %H:%M') if s.created_at else "—",
            "device": s.device.name if s.device else "—",
            "project": s.device.project.name if s.device and s.device.project else "—"
        }
        for s in sns
    ]


@router.post("/models")
async def create_model(data: ModelCreateInput, db: Session = Depends(get_db)):
    """Создать новую модель устройства."""
    if not data.name or not data.sn_prefix:
        raise HTTPException(400, "Название и префикс обязательны")
        
    exists = db.query(DeviceModel).filter_by(category=data.category, name=data.name).first()
    if exists:
        raise HTTPException(400, f"Модель '{data.name}' уже существует в этой категории")
        
    new_model = DeviceModel(
        category=data.category,
        name=data.name,
        sn_prefix=data.sn_prefix
    )
    db.add(new_model)
    db.commit()
    return {"ok": True, "message": f"Модель '{data.name}' добавлена"}


@router.post("/models/{model_id}/counter")
async def set_counter(model_id: int, data: CounterSetInput, db: Session = Depends(get_db)):
    """Установить якорь счетчика."""
    model = db.query(DeviceModel).get(model_id)
    if not model:
        raise HTTPException(404, "Модель не найдена")
        
    new_sn_str = f"{model.sn_prefix}{data.count:05d}"
    
    # Резервируем SN как неиспользованный
    new_sn = SerialNumber(
        sn=new_sn_str,
        model_id=model.id,
        is_used=False,
        created_at=datetime.now()
    )
    db.add(new_sn)
    db.commit()
    return {"ok": True, "message": f"Счетчик установлен. Следующий сгенерированный будет > {new_sn_str}"}
