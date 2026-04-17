"""
API эндпоинты для Admin — CRUD пользователей.
Полный функционал как в десктопной admin_tab.py:
- Список пользователей
- Создание пользователя
- Редактирование (имя, фамилия, роль, пароль)
- Блокировка / Разблокировка
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re
import json

from src.database import get_db
from src.models import User, WorkLog, SystemConfig
from src.system_config import get_all_settings, set_config
from web.dependencies import get_current_user

router = APIRouter()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    first_name: str = Field("", max_length=150)
    last_name: str = Field("", max_length=150)
    password: str = Field(..., min_length=4)
    role: str = Field("WORKER", pattern='^(ADMIN|MANAGER|SHOP_MANAGER|EMPLOYEE|WORKER)$')

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('username must be alphanumeric (plus _ or -)')
        return v


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=150)
    last_name: Optional[str] = Field(None, max_length=150)
    role: Optional[str] = Field(None, pattern='^(ADMIN|MANAGER|SHOP_MANAGER|EMPLOYEE|WORKER)$')
    new_password: Optional[str] = Field(None, min_length=4)


@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    """Получить всех пользователей (root скрыт)."""
    users = db.query(User).filter(User.role != 'ROOT').order_by(User.date_joined.desc()).all()
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "full_name": u.full_name,
            "role": u.role,
            "role_display": u.role_display,
            "is_active": u.is_active,
            "date_joined": u.date_joined.strftime('%d.%m.%Y %H:%M') if u.date_joined else "—",
        }
        for u in users
    ]


@router.post("/users")
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    """Создать нового пользователя."""
    if not data.username or not data.password:
        raise HTTPException(400, "Логин и пароль обязательны")

    exists = db.query(User).filter(User.username == data.username).first()
    if exists:
        raise HTTPException(400, "Сотрудник с таким логином уже существует")

    new_user = User(
        username=data.username,
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
        is_active=True,
        date_joined=datetime.now(),
    )
    new_user.set_password(data.password)
    db.add(new_user)
    db.commit()
    return {"ok": True, "message": f"Сотрудник \"{data.username}\" создан"}


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    """Редактировать пользователя."""
    user = db.query(User).get(user_id)
    if not user or user.role == 'ROOT':
        raise HTTPException(404, "Пользователь не найден")

    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.role is not None:
        user.role = data.role
    if data.new_password:
        user.set_password(data.new_password)

    db.commit()
    return {"ok": True, "message": f"Данные \"{user.username}\" обновлены"}


@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(user_id: int, db: Session = Depends(get_db)):
    """Блокировка / Разблокировка пользователя."""
    user = db.query(User).get(user_id)
    if not user or user.role == 'ROOT':
        raise HTTPException(404, "Пользователь не найден")

    user.is_active = not user.is_active
    db.commit()

    action = "разблокирован" if user.is_active else "заблокирован"
    return {"ok": True, "message": f"Сотрудник \"{user.username}\" {action}", "is_active": user.is_active}


@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    """Получить статистику для админки."""
    total_users = db.query(User).filter(User.role != 'ROOT').count()
    active_users = db.query(User).filter_by(is_active=True).filter(User.role != 'ROOT').count()
    total_worklogs = db.query(WorkLog).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_worklogs": total_worklogs,
    }


# =============================================
# Настройки системы (ROOT only)
# =============================================

class SettingsUpdate(BaseModel):
    route_bypass_roles: List[str]
    cooldown_bypass_roles: List[str]


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Системные настройки — только ROOT."""
    if current_user.role != 'ROOT':
        raise HTTPException(403, "Доступ запрещён")
    return get_all_settings(db)


@router.put("/settings")
def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить системные настройки — только ROOT."""
    if current_user.role != 'ROOT':
        raise HTTPException(403, "Доступ запрещён")

    # Санитизация: допустимые роли (без ROOT)
    ALLOWED = {'ADMIN', 'MANAGER', 'SHOP_MANAGER', 'EMPLOYEE', 'WORKER'}
    route_roles  = [r for r in data.route_bypass_roles  if r in ALLOWED]
    cool_roles   = [r for r in data.cooldown_bypass_roles if r in ALLOWED]

    set_config(db, 'route_bypass_roles',    route_roles)
    set_config(db, 'cooldown_bypass_roles', cool_roles)

    return {"ok": True, "message": "Настройки сохранены"}
