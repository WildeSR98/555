# 🔍 Аудит проекта Production Manager

> Дата: 24.04.2026 | Файлов проверено: 15 API + models + workflow + dependencies

---

## 🔴 Критические баги

### 1. Дублирование ключа `QC_PASSED` в `STATUS_DISPLAY` (models.py:305,314)

```python
STATUS_DISPLAY = {
    ...
    'QC_PASSED': 'Контроль пройден',    # ← строка 305
    ...
    'QC_PASSED': 'Склад (Завершено)',   # ← строка 314, ПЕРЕЗАПИСЫВАЕТ первый!
}
```

**Проблема:** В Python-словаре дублирующийся ключ молча перезаписывает предыдущий. Отображение `QC_PASSED` всегда будет `Склад (Завершено)`, а не `Контроль пройден`.

**Рекомендация:** Удалить строку 305 (оставить только 314).

---

### 2. Проверка заголовка MAC-файла идёт ПОСЛЕ нормализации (mac_pool_api.py:245)

```python
for mac_raw in rows:
    mac = normalize_mac(mac_raw)       # ← "MAC" → None (12 hex нет)
    if not mac:
        skipped_bad += 1               # ← заголовок "MAC" считается ошибкой формата
        continue
    if mac_raw.upper() in ('MAC', 'MAC ADDRESS', 'ADDRESS'):  # ← никогда не выполнится!
        continue
```

**Проблема:** Проверка заголовка `mac_raw.upper() in ('MAC', ...)` стоит **после** `normalize_mac()`. Если MAC-строка = "MAC", normalize вернёт `None`, счётчик `skipped_bad` увеличится, и до проверки заголовка код не дойдёт. Не баг-крашер, но `skipped_bad` искажается.

**Рекомендация:** Перенести проверку заголовка **перед** `normalize_mac()`.

---

### 3. `_assign_manual_mac` не обрабатывает случай «MAC уже используется другим устройством» (projects_api.py:129-136)

```python
def _assign_manual_mac(db, raw, device_id):
    ...
    existing = db.query(MacAddress).filter_by(mac=mac_val).first()
    if not existing:
        db.add(...)        # новый — ОК
    elif not existing.is_used:
        existing.is_used = True
        existing.device_id = device_id   # свободный — ОК
    return mac_val   # ← если MAC уже USED — тихо возвращает mac_val,
                     #    НО в БД он привязан к другому устройству!
```

**Проблема:** Если пользователь вручную вводит MAC, который уже занят другим устройством (`is_used=True, device_id=другой`), функция молча возвращает его не перепривязывая. В Excel будет этот MAC, но привязка в БД останется к старому устройству.

**Рекомендация:** Добавить `raise ValueError(f"MAC {mac_val} уже используется устройством #{existing.device_id}")` или предупреждение.

---

### 4. `require_manager` не включает ROOT (dependencies.py:43)

```python
def require_manager(user):
    if user.role not in (User.ROLE_ADMIN, User.ROLE_MANAGER, 'SHOP_MANAGER'):
        raise HTTPException(403, ...)
```

**Проблема:** ROOT (суперадмин) не может пройти эту проверку. Хотя ROOT должен иметь доступ ко всему.

**Рекомендация:** Добавить `User.ROLE_ROOT` в кортеж.

---

## 🟡 Логические ошибки и несогласованности

### 5. Комментарий в `MacAddress` модели устарел (models.py:725)

```python
class MacAddress(Base):
    """
    mac_type:
      'LAN'   — встроенный сетевой интерфейс
      'IDRAC' — iDRAC / BMC (только для TIOGA, SERVAL, OCTOPUS)
    """
```

**Проблема:** Система теперь использует **только LAN** (iDRAC/BMC убран из фронтенда), но модель и комментарий ещё содержат `IDRAC`.

---

### 6. `DUAL_MAC_CATEGORIES` и `SINGLE_MAC_CATEGORIES` ещё разделяют MAC на LAN/BMC (models.py:22-24)

```python
DUAL_MAC_CATEGORIES   = {'TIOGA', 'SERVAL', 'OCTOPUS'}
SINGLE_MAC_CATEGORIES = {'PC'}
```

**Проблема:** Пользователь ранее отказался от разделения LAN/BMC, но код в `projects_api.py` всё ещё использует `needs_mac2 = cat in DUAL_MAC_CATEGORIES` для назначения **двух** MAC. Это может быть корректно (2 LAN MAC вместо LAN+BMC), но стоит убедиться что это намерение, а не артефакт.

---

### 7. `archive_api.py` не проверяет права `current_user` на `create_user/update_user` (admin_api.py:70-111)

```python
@router.post("/users")
def create_user(data: UserCreate, db: Session = Depends(get_db)):  # ← нет проверки get_current_user!
```

**Проблема:** Эндпоинты `POST /api/admin/users` и `PUT /api/admin/users/{id}` не требуют авторизацию через `get_current_user`. Любой авторизованный пользователь (даже WORKER) может создавать и редактировать пользователей через прямой API-запрос. Защита только на уровне UI.

> [!CAUTION]
> Это **уязвимость безопасности**. Рядовой работник может через curl/fetch создать себе ADMIN-аккаунт.

---

### 8. `toggle_user_active` тоже без авторизации (admin_api.py:114)

```python
@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(user_id: int, db: Session = Depends(get_db)):  # ← нет get_current_user
```

**Та же проблема:** Любой авторизованный пользователь может заблокировать/разблокировать кого угодно.

---

### 9. Дублирование `net_devices` (projects_api.py:471-480)

```python
net_devices = [
    {'part_number': d.part_number, 'serial_number': d.serial_number}
    for d in new_proj.devices
]                                  # ← Создано, но НИКОГДА не используется!

folder_result = _mod.create_project_folders(
    project_name=new_proj.name,
    devices=[                      # ← Ещё раз тот же list comprehension
        {'part_number': d.part_number, 'serial_number': d.serial_number}
        for d in new_proj.devices
    ],
)
```

**Проблема:** Переменная `net_devices` создана, но не используется. Список дублируется.

---

### 10. `logger.warn` → `logger.warning` (health_api.py:36)

```python
logger.warn(f"Health check: Low disk space ({free_gb:.2f} GB free)")
```

**Проблема:** `logger.warn()` — deprecated в Python 3.x. Следует использовать `logger.warning()`.

---

### 11. Избыточная проверка после STRICT_TRANSITIONS (workflow.py:84-90)

```python
# Сначала проверяется STRICT_TRANSITIONS (строка 79)
if old_status in WorkflowEngine.STRICT_TRANSITIONS:
    allowed = WorkflowEngine.STRICT_TRANSITIONS[old_status]
    if new_status not in allowed:
        return False, "Нарушение маршрута..."

# Потом отдельно проверяется то же самое (строка 85):
if old_status == 'ASSEMBLY' and new_status not in [...]:
     return False, "После сборки..."
```

**Проблема:** Вторая проверка (строки 84-90) дублирует то, что уже проверено в `STRICT_TRANSITIONS`. Если `ASSEMBLY` → не `WAITING_VIBROSTAND`, первая проверка уже вернёт `False`. Вторая проверка мертвый код.

---

### 12. `Workplace.TYPE_DISPLAY` не включает WAREHOUSE (models.py:471-481)

```python
TYPE_DISPLAY = {
    'PRE_PRODUCTION': 'Комплектовка',
    ...
    'REPAIR': 'Ремонтный стенд',
    # 'WAREHOUSE' — отсутствует!
}
```

**Проблема:** Если рабочее место типа `WAREHOUSE`, `type_display` вернёт сырой ключ `WAREHOUSE` вместо `Склад`.

---

## 🟢 Мелкие замечания

### 13. Опечатка в комментарии (models.py:85)

```python
ROLE_ROOT = 'ROOT'  # Скрытая системная рольь, не отображается в UI
#                                     ^^^^^ — лишняя «ь»
```

### 14. Неиспользуемый import `or_` (devices_api.py:7)

```python
from sqlalchemy import or_   # ← нигде не используется
```

### 15. `mac_pool_api.py:213` — аннотация типа `rows: list[tuple[str, str]]` неверна

```python
rows: list[tuple[str, str]] = []   # [(mac_raw, type_raw)]
```

Но затем в rows добавляется просто `mac_raw` (строка 224, 237) — `str`, не `tuple[str, str]`.

---

## 📋 Сводная таблица

| # | Файл | Серьёзность | Описание |
|---|---|---|---|
| 1 | models.py:305,314 | 🔴 Баг | Дубль ключа `QC_PASSED` |
| 2 | mac_pool_api.py:245 | 🟡 Мелкий | Проверка заголовка после нормализации |
| 3 | projects_api.py:129 | 🔴 Баг | Ручной MAC занятый другим — тихо игнорируется |
| 4 | dependencies.py:43 | 🟡 Логика | ROOT не в `require_manager` |
| 5 | models.py:725 | 🟢 Доки | Устаревший комментарий IDRAC |
| 6 | models.py:22 | 🟡 Логика | DUAL_MAC всё ещё разделяет, хотя BMC убран |
| 7 | admin_api.py:70 | 🔴 Безопасность | `create_user` без проверки прав |
| 8 | admin_api.py:114 | 🔴 Безопасность | `toggle_user_active` без проверки прав |
| 9 | projects_api.py:471 | 🟢 Мусор | Неиспользуемая `net_devices` |
| 10 | health_api.py:36 | 🟢 Deprecated | `logger.warn` → `logger.warning` |
| 11 | workflow.py:84-90 | 🟡 Мёртвый код | Дублирующая проверка после STRICT_TRANSITIONS |
| 12 | models.py:471 | 🟡 Неполнота | WAREHOUSE нет в `TYPE_DISPLAY` |
| 13 | models.py:85 | 🟢 Опечатка | «рольь» |
| 14 | devices_api.py:7 | 🟢 Мусор | Неиспользуемый import `or_` |
| 15 | mac_pool_api.py:213 | 🟢 Типы | Неверная аннотация `list[tuple]` |

---

## ✅ Что реализовано корректно

- **Workflow-транзакции** (`scan_api.py`): правильная проверка маршрутов, буферизация, resolve_next_status
- **Пароли Django** (`check_password/set_password`): корректная совместимость pbkdf2_sha256
- **WebSocket** (`ws_manager.py`): стабильный ping/pong, reconnect, broadcast
- **Архивация** (`archive_api.py`): 30-дневный hold period, force mode с паролем, перемещение папок
- **CSRF-защита** через `fastapi-csrf-protect`
- **Session-based auth** — корректная реализация через middleware
