"""
Хелпер для чтения и записи системных настроек (SystemConfig).
ROOT управляет, остальные только читают.

Настройки:
  route_bypass_roles   — роли, которым разрешён обход маршрута постов
  cooldown_bypass_roles — роли, которым разрешён обход кулдауна (5 мин)
"""
import json
from typing import List

# Значения по умолчанию (если запись в БД ещё не создана)
_DEFAULTS: dict = {
    'route_bypass_roles':    ['ADMIN', 'MANAGER', 'SHOP_MANAGER'],
    'cooldown_bypass_roles': ['ADMIN', 'MANAGER', 'SHOP_MANAGER'],
}

# ROOT всегда привилегирован — не вносится в настройки, добавляется динамически
_ALWAYS_PRIVILEGED = {'ROOT'}


def _get_raw(db, key: str):
    from src.models import SystemConfig
    cfg = db.query(SystemConfig).filter_by(key=key).first()
    if cfg and cfg.value:
        return json.loads(cfg.value)
    return _DEFAULTS.get(key, [])


def get_route_bypass_roles(db) -> List[str]:
    """Роли, которые могут принимать устройство на любой пост (обход маршрута)."""
    roles = list(_get_raw(db, 'route_bypass_roles'))
    roles += [r for r in _ALWAYS_PRIVILEGED if r not in roles]
    return roles


def get_cooldown_bypass_roles(db) -> List[str]:
    """Роли, которые не ограничены кулдауном при смене статуса."""
    roles = list(_get_raw(db, 'cooldown_bypass_roles'))
    roles += [r for r in _ALWAYS_PRIVILEGED if r not in roles]
    return roles


def set_config(db, key: str, value) -> None:
    """Записывает настройку в БД."""
    from src.models import SystemConfig
    from datetime import datetime
    cfg = db.query(SystemConfig).filter_by(key=key).first()
    if cfg:
        cfg.value = json.dumps(value)
        cfg.updated_at = datetime.now()
    else:
        cfg = SystemConfig(key=key, value=json.dumps(value), updated_at=datetime.now())
        db.add(cfg)
    db.commit()


def get_all_settings(db) -> dict:
    """Возвращает все настройки для UI."""
    return {
        'route_bypass_roles':    _get_raw(db, 'route_bypass_roles'),
        'cooldown_bypass_roles': _get_raw(db, 'cooldown_bypass_roles'),
    }
