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
from src.models import Device, DeviceModel, SerialNumber, DeviceCategory

router = APIRouter()

class ModelCreateInput(BaseModel):
    category: str
    name: str
    sn_prefix: str

class CounterSetInput(BaseModel):
    count: int

class ModelUpdateInput(BaseModel):
    name: str

class CategoryCreateInput(BaseModel):
    code: str          # Внутренний код, напр. 'SERVAL2'
    display_name: str  # Отображаемое имя
    sn_prefix: str     # Префикс SN

class CategoryUpdateInput(BaseModel):
    display_name: str
    sn_prefix: str


@router.patch("/models/{model_id}")
def update_model(model_id: int, data: ModelUpdateInput, db: Session = Depends(get_db)):
    """Переименовать модель устройства."""
    model = db.query(DeviceModel).get(model_id)
    if not model:
        raise HTTPException(404, "Модель не найдена")
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Название не может быть пустым")
    # Проверка на дубликат в той же категории
    dup = db.query(DeviceModel).filter_by(category=model.category, name=name).first()
    if dup and dup.id != model_id:
        raise HTTPException(400, f"Модель «{name}» уже существует в этой категории")
    model.name = name
    db.commit()
    return {"ok": True, "message": f"Модель переименована в «{name}»"}


@router.get("/tree")
def get_sn_tree(db: Session = Depends(get_db)):
    """Получить дерево Категория -> Модель (DB-first)."""
    models = db.query(DeviceModel).order_by(DeviceModel.category, DeviceModel.name).all()
    db_cats = {c.code: c for c in db.query(DeviceCategory).order_by(DeviceCategory.sort_order, DeviceCategory.code).all()}

    # Категории из ВД: все у кого есть sn_prefix
    cats = {}
    for code, cat in db_cats.items():
        if cat.sn_prefix:
            cats[code] = {"id": code, "name": cat.display_name, "models": []}

    # Модели → по категориям
    for m in models:
        if m.category in cats:
            cats[m.category]["models"].append({
                "id": m.id, "name": m.name, "prefix": m.sn_prefix
            })

    return list(cats.values())


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """Все категории для форм (из ВД)."""
    cats = db.query(DeviceCategory).order_by(DeviceCategory.sort_order, DeviceCategory.code).all()
    return [
        {"id": c.code, "name": c.display_name, "prefix": c.sn_prefix or "", "has_prefix": bool(c.sn_prefix)}
        for c in cats
    ]


@router.post("/categories")
def create_category(data: CategoryCreateInput, db: Session = Depends(get_db)):
    """Создать новую категорию устройств."""
    code = data.code.strip().upper()
    if not code or not data.display_name.strip():
        raise HTTPException(400, "Код и название обязательны")
    if db.query(DeviceCategory).filter_by(code=code).first():
        raise HTTPException(400, f"Категория «{code}» уже существует")
    db.add(DeviceCategory(
        code=code,
        display_name=data.display_name.strip(),
        sn_prefix=data.sn_prefix.strip() or None,
        sort_order=200,
    ))
    db.commit()
    return {"ok": True, "message": f"Категория «{data.display_name}» (код: {code}) добавлена"}


@router.patch("/categories/{code}")
def update_category(code: str, data: CategoryUpdateInput, db: Session = Depends(get_db)):
    """Переименовать / обновить категорию."""
    cat = db.query(DeviceCategory).filter_by(code=code).first()
    if not cat:
        raise HTTPException(404, f"Категория «{code}» не найдена")
    if not data.display_name.strip():
        raise HTTPException(400, "Название не может быть пустым")
    cat.display_name = data.display_name.strip()
    cat.sn_prefix    = data.sn_prefix.strip() or None
    db.commit()
    return {"ok": True, "message": f"Категория обновлена"}


@router.get("/models/{model_id}/sns")
def get_model_sns(model_id: int, sn: str = "", db: Session = Depends(get_db)):
    """Получить все SN для конкретной модели (с поиском)."""
    from sqlalchemy.orm import joinedload
    query = db.query(SerialNumber).options(
        joinedload(SerialNumber.device).joinedload(Device.project)
    ).filter(SerialNumber.model_id == model_id)
    
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
def create_model(data: ModelCreateInput, db: Session = Depends(get_db)):
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
def set_counter(model_id: int, data: CounterSetInput, db: Session = Depends(get_db)):
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
