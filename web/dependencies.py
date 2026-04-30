import json
from fastapi import Request, HTTPException, Depends, Response
from sqlalchemy.orm import Session
from src.database import get_session
from src.models import User, SystemConfig
from fastapi_csrf_protect import CsrfProtect

# ── Nav tabs definition (order = sidebar order) ───────────────────────────────
ALL_NAV_TABS = [
    {"key": "dashboard", "label": "📊 Дашборд",    "url": "/dashboard"},
    {"key": "analytics", "label": "📈 Аналитика",  "url": "/analytics"},
    {"key": "projects",  "label": "📁 Проекты",    "url": "/projects"},
    {"key": "pipeline",  "label": "🔄 Конвейер",   "url": "/pipeline"},
    {"key": "scan",      "label": "📷 Скан",       "url": "/scan"},
    {"key": "devices",   "label": "🔧 Устройства", "url": "/devices"},
    {"key": "sn_pool",   "label": "🏷️ SN Пул",    "url": "/sn-pool"},
    {"key": "routes",    "label": "📋 Маршруты",   "url": "/route-configs"},
    {"key": "archive",   "label": "📦 Архив",      "url": "/archive"},
    {"key": "admin",     "label": "⚙️ Админ",      "url": "/admin"},
]

_ADMIN_TAB_ROLES = {'ADMIN', 'ROOT', 'SHOP_MANAGER'}


def get_nav_tabs(user_role: str) -> list:
    """Return ordered list of tab dicts visible for the given role.

    Logic:
    - ROOT → always all tabs
    - Role in nav_permissions config → only listed tabs
    - No config for role → all tabs; admin tab only for ADMIN/ROOT/SHOP_MANAGER
    """
    if user_role == 'ROOT':
        return list(ALL_NAV_TABS)

    try:
        with get_session() as session:
            cfg = session.query(SystemConfig).filter_by(key='nav_permissions').first()
            nav_perms = json.loads(cfg.value) if cfg and cfg.value else {}
    except Exception:
        nav_perms = {}

    if user_role in nav_perms:
        allowed = set(nav_perms[user_role])
        return [t for t in ALL_NAV_TABS if t['key'] in allowed]

    # Default: all tabs; admin only for privileged roles
    if user_role in _ADMIN_TAB_ROLES:
        return list(ALL_NAV_TABS)
    return [t for t in ALL_NAV_TABS if t['key'] != 'admin']


def get_current_user(request: Request) -> User:
    """Получает текущего пользователя из сессии (Синхронно)."""
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
    if user.role not in (User.ROLE_ADMIN, User.ROLE_ROOT, User.ROLE_MANAGER, 'SHOP_MANAGER'):
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

    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()

    context["request"] = request
    context["csrf_token"] = csrf_token
    if "user" not in context:
        context["user"] = get_current_user(request)

    # Добавляем отфильтрованные вкладки в контекст
    if "nav_tabs" not in context and context.get("user"):
        context["nav_tabs"] = get_nav_tabs(context["user"].role)

    response = templates.TemplateResponse(template_name, context)
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response
