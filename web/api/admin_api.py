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
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
def create_user(data: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Создать нового пользователя. Только ADMIN/ROOT."""
    if current_user.role not in (User.ROLE_ADMIN, User.ROLE_ROOT):
        raise HTTPException(403, "Недостаточно прав для создания пользователей")

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
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Редактировать пользователя. Только ADMIN/ROOT."""
    if current_user.role not in (User.ROLE_ADMIN, User.ROLE_ROOT):
        raise HTTPException(403, "Недостаточно прав для редактирования пользователей")
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
def toggle_user_active(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Блокировка / Разблокировка пользователя. Только ADMIN/ROOT."""
    if current_user.role not in (User.ROLE_ADMIN, User.ROLE_ROOT):
        raise HTTPException(403, "Недостаточно прав для блокировки пользователей")
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


# ─── Nav Permissions (ROOT only) ─────────────────────────────────────────────

class NavPermissionsInput(BaseModel):
    permissions: dict  # {"WORKER": ["scan", "dashboard"], ...}


@router.get("/nav-permissions")
def get_nav_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Настройки видимости вкладок по ролям — только ROOT."""
    if current_user.role != 'ROOT':
        raise HTTPException(403, "Доступ запрещён")
    cfg = db.query(SystemConfig).filter_by(key='nav_permissions').first()
    if cfg and cfg.value:
        return json.loads(cfg.value)
    return {}


@router.put("/nav-permissions")
def update_nav_permissions(
    data: NavPermissionsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить видимость вкладок по ролям — только ROOT."""
    if current_user.role != 'ROOT':
        raise HTTPException(403, "Доступ запрещён")

    from web.dependencies import ALL_NAV_TABS
    ALLOWED_ROLES = {'ADMIN', 'MANAGER', 'SHOP_MANAGER', 'EMPLOYEE', 'WORKER'}
    ALLOWED_TABS  = {t['key'] for t in ALL_NAV_TABS}

    cleaned = {
        role: [tab for tab in tabs if tab in ALLOWED_TABS]
        for role, tabs in data.permissions.items()
        if role in ALLOWED_ROLES
    }

    cfg = db.query(SystemConfig).filter_by(key='nav_permissions').first()
    if cfg:
        cfg.value      = json.dumps(cleaned, ensure_ascii=False)
        cfg.updated_at = datetime.now()
    else:
        db.add(SystemConfig(
            key='nav_permissions',
            value=json.dumps(cleaned, ensure_ascii=False),
            updated_at=datetime.now(),
        ))
    db.commit()
    return {"ok": True, "message": "Видимость вкладок сохранена"}


# =============================================
# Загрузка изображений на сетевой диск
# =============================================

from fastapi import UploadFile, File, Form
from typing import List as TList
import shutil, os
from pathlib import Path

IMG_TARGET_DIR = Path(os.getenv('IMG_TARGET_DIR', r'\\server\share\photos'))
IMG_EXTENSIONS = {f".{e.strip().lower()}" for e in os.getenv('IMG_EXTENSIONS', 'jpg,jpeg,png,bmp,gif,webp,tiff,tif').split(',')}


@router.post("/upload-images")
async def upload_images(
    files: TList[UploadFile] = File(...),
    subdir: str = Form(default=''),
    open_explorer: str = Form(default='false'),   # 'true' → открыть Explorer
    current_user: User = Depends(get_current_user),
):
    """
    Загрузить изображения с браузера на сетевой диск (IMG_TARGET_DIR/{subdir}/).
    Доступно для всех авторизованных пользователей.
    subdir — подпапка внутри target (обычно SN устройства).
    open_explorer — открыть папку в Windows Explorer после загрузки.
    """
    dest = IMG_TARGET_DIR / subdir.strip() if subdir.strip() else IMG_TARGET_DIR

    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(500, f"Не удалось создать папку {dest}: {e}")

    results = []
    for upload in files:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in IMG_EXTENSIONS:
            results.append({"file": upload.filename, "ok": False, "error": "Недопустимый формат"})
            continue

        dest_file = dest / upload.filename
        # Если файл существует — добавляем метку времени
        if dest_file.exists():
            stem = Path(upload.filename).stem
            ts = datetime.now().strftime('%H%M%S')
            dest_file = dest / f"{stem}_{ts}{suffix}"

        try:
            with dest_file.open('wb') as f:
                shutil.copyfileobj(upload.file, f)
            results.append({"file": upload.filename, "ok": True, "saved_as": dest_file.name})
        except Exception as e:
            results.append({"file": upload.filename, "ok": False, "error": str(e)})
        finally:
            await upload.close()

    ok_count  = sum(1 for r in results if r['ok'])
    err_count = len(results) - ok_count

    # Открываем папку в Explorer (работает если сервер локальный)
    if open_explorer.lower() in ('true', '1') and ok_count > 0:
        try:
            import subprocess as _sp
            _sp.Popen(f'explorer "{dest}"')
        except Exception:
            pass  # не критично если не открылось

    return {
        "ok":      err_count == 0,
        "copied":  ok_count,
        "errors":  err_count,
        "message": f"Загружено: {ok_count}, ошибок: {err_count}",
        "target":  str(dest),
        "results": results,
    }


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.get('/logs')
def get_logs(
    level: str = 'ERROR',       # ERROR | WARNING | ALL
    limit: int = 200,
    user: User = Depends(get_current_user),
):
    """Читает последние N строк лог-файла, фильтруя по уровню."""
    from pathlib import Path as _Path
    import re as _re

    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, 'Недостаточно прав')

    log_file = _Path(__file__).resolve().parent.parent.parent / 'logs' / 'production_manager.log'
    if not log_file.exists():
        return {'ok': True, 'entries': [], 'total': 0}

    level_upper = level.upper()
    allowed_levels = {'ERROR', 'WARNING', 'CRITICAL', 'ALL'}
    if level_upper not in allowed_levels:
        level_upper = 'ERROR'

    pattern = _re.compile(
        r'^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(?P<level>\w+)\s*\|\s*(?P<logger>\S+)\s*\|\s*(?P<msg>.+)$'
    )

    entries = []
    try:
        with open(log_file, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        raise HTTPException(500, f'Ошибка чтения лога: {e}')

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if not m:
            continue
        lvl = m.group('level').upper()
        if level_upper != 'ALL' and lvl != level_upper:
            continue
        entries.append({
            'dt':     m.group('dt'),
            'level':  lvl,
            'logger': m.group('logger'),
            'msg':    m.group('msg'),
        })
        if len(entries) >= limit:
            break

    return {'ok': True, 'entries': entries, 'total': len(entries), 'log_file': str(log_file)}
