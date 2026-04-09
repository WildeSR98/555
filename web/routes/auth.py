"""
Авторизация и управление сессиями в веб-интерфейсе.
Использует ту же модель User из PostgreSQL.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from src.database import get_session
from src.models import User
from src.config import config
from pathlib import Path

router = APIRouter()

# Секрет для сессий — строка для SessionMiddleware
SECRET_KEY = str(config.db.db_password) if config.db.db_password else "production-manager-secret-key"
SECRET_KEY = SECRET_KEY.encode('utf-8') if isinstance(SECRET_KEY, str) else SECRET_KEY

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


def get_current_user(request: Request) -> User | None:
    """Получить текущего пользователя из сессии."""
    user_id = request.session.get("user_id")
    if user_id:
        db = get_session()
        try:
            return db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()
    return None


@router.get("/login")
async def login_page(request: Request):
    """Страница входа."""
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    """Обработка входа."""
    import hashlib
    
    user = db.query(User).filter(
        (User.username == username) | (User.action_pin == username)
    ).first()
    
    if user and user.check_password(password):
        request.session["user_id"] = user.id
        request.session["username"] = user.username
        return RedirectResponse(url="/dashboard", status_code=303)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Неверный логин или пароль",
    })


@router.get("/logout")
async def logout(request: Request):
    """Выход из системы."""
    request.session.clear()
    return RedirectResponse(url="/login")
