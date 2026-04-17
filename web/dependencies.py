from fastapi import Request, HTTPException, Depends, Response
from sqlalchemy.orm import Session
from src.database import get_session
from src.models import User
from fastapi_csrf_protect import CsrfProtect

def get_current_user(request: Request) -> User:
    """
    Получает текущего пользователя из сессии (Синхронно).
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Inactive user")
        
        return user


async def get_current_user_optional(request: Request, db=None) -> User | None:
    """Возвращает пользователя или None (без исключения). Используется в HTML-роутах."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        return user if user and user.is_active else None


def require_admin(user: User = Depends(get_current_user)):
    """Проверяет, является ли пользователь администратором или root (Синхронно)."""
    if user.role not in (User.ROLE_ADMIN, User.ROLE_ROOT):
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
    return user

def require_manager(user: User = Depends(get_current_user)):
    """Проверяет, является ли пользователь менеджером или админом (Синхронно)."""
    if user.role not in (User.ROLE_ADMIN, User.ROLE_MANAGER, 'SHOP_MANAGER'):
        raise HTTPException(status_code=403, detail="Forbidden: Manager access required")
    return user

def setup_csrf(request: Request, csrf_protect: CsrfProtect, response: Response) -> str:
    """Генерирует CSRF токен и устанавливает куку в ответ."""
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    csrf_protect.set_csrf_cookie(signed_token, response)
    return csrf_token

def render_template(template_name: str, context: dict, request: Request, csrf_protect: CsrfProtect):
    """Обертка для рендеринга шаблонов с CSRF и пользователем."""
    from web.main import templates
    
    # Генерируем CSRF
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    
    # Добавляем в контекст
    context["request"] = request
    context["csrf_token"] = csrf_token
    if "user" not in context:
        context["user"] = get_current_user(request)
        
    response = templates.TemplateResponse(template_name, context)
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response
