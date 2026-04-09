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
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from src.database import get_db
from src.models import User, WorkLog

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    first_name: str = ""
    last_name: str = ""
    password: str
    role: str = "WORKER"


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    new_password: Optional[str] = None


@router.get("/users")
async def get_users(db: Session = Depends(get_db)):
    """Получить всех пользователей."""
    users = db.query(User).order_by(User.date_joined.desc()).all()
    
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
async def create_user(data: UserCreate, db: Session = Depends(get_db)):
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
async def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    """Редактировать пользователя."""
    user = db.query(User).get(user_id)
    if not user:
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
async def toggle_user_active(user_id: int, db: Session = Depends(get_db)):
    """Блокировка / Разблокировка пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    user.is_active = not user.is_active
    db.commit()

    action = "разблокирован" if user.is_active else "заблокирован"
    return {"ok": True, "message": f"Сотрудник \"{user.username}\" {action}", "is_active": user.is_active}


@router.get("/stats")
async def get_admin_stats(db: Session = Depends(get_db)):
    """Получить статистику для админки."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter_by(is_active=True).count()
    total_worklogs = db.query(WorkLog).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_worklogs": total_worklogs,
    }
