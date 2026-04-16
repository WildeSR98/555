"""
Авторизация и управление сессиями в веб-интерфейсе.
Использует ту же модель User из PostgreSQL.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_csrf_protect import CsrfProtect
from starlette.responses import Response
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from src.database import get_session, get_db
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
async def login_page(request: Request, csrf_protect: CsrfProtect = Depends()):
    """Страница входа."""
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "csrf_token": csrf_token
    })
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.post("/login")
async def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    csrf_protect: CsrfProtect = Depends(),
):
    """Обработка входа."""
    # Сначала распарсим форму вручную, чтобы validate_csrf мог её прочитать
    form_data = await request.form()
    username = form_data.get("username", "")
    password = form_data.get("password", "")
    
    # Валидация CSRF-токена из формы
    try:
        await csrf_protect.validate_csrf(request)
    except Exception as e:
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
        response = templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"Ошибка CSRF-защиты: {str(e)}",
            "csrf_token": csrf_token
        })
        csrf_protect.set_csrf_cookie(signed_token, response)
        return response
    
    import hashlib

    user = db.query(User).filter(
        (User.username == username) | (User.action_pin == username)
    ).first()

    if user and user.check_password(password):
        request.session["user_id"] = user.id
        request.session["username"] = user.username
        return RedirectResponse(url="/dashboard", status_code=303)

    # При ошибке аутентификации возвращаем форму с токеном
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Неверный логин или пароль",
        "csrf_token": csrf_token
    })
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.get("/logout")
async def logout(request: Request):
    """Выход из системы."""
    request.session.clear()
    return RedirectResponse(url="/login")
