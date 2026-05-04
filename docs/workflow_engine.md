# Workflow Engine — Логика переходов статусов

## Назначение
`WorkflowEngine` (`src/logic/workflow.py`) определяет:
1. Допустимые переходы между статусами устройств
2. Cooldown (минимальное время на этапе)
3. Может ли рабочий пост принять устройство
4. Лимиты буфера (batch limit)

## Конвейер статусов

```
WAITING_KITTING → PRE_PRODUCTION/KITTING → WAITING_ASSEMBLY → ASSEMBLY
→ WAITING_VIBROSTAND → VIBROSTAND → WAITING_TECH_CONTROL_1_1 → TECH_CONTROL_1_1
→ WAITING_TECH_CONTROL_1_2 → TECH_CONTROL_1_2 → WAITING_FUNC_CONTROL → FUNC_CONTROL
→ WAITING_TECH_CONTROL_2_1 → TECH_CONTROL_2_1 → WAITING_TECH_CONTROL_2_2 → TECH_CONTROL_2_2
→ WAITING_PACKING → PACKING → WAITING_ACCOUNTING → ACCOUNTING
→ WAITING_WAREHOUSE → WAREHOUSE → QC_PASSED
```

Боковые ветки: `DEFECT`, `REPAIR`

## Проверка перехода (`can_change_status`)

```python
WorkflowEngine.can_change_status(device, new_status, user, last_log,
    cooldown_bypass_roles, cooldown_seconds)
→ (bool, str)  # ok, error_message
```

**Порядок проверок:**

1. **Привилегированные роли** — ADMIN, MANAGER, SHOP_MANAGER, ROOT пропускают все проверки
2. **Cooldown** — `time_passed < cooldown_seconds` → «Ожидайте таймер. Осталось M:SS»
3. **Логика переходов** — проверка по `STRICT_TRANSITIONS` dict

**Настройка cooldown_bypass_roles:**
Хранится в таблице `pm_system_config` (ключ `cooldown_bypass_roles`).
Получается через `get_cooldown_bypass_roles(db)` из `src/system_config.py`.

## Проверка приёма на пост (`can_accept_device`)

```python
WorkflowEngine.can_accept_device(workplace_type, device_status)
→ (bool, str)
```

**Правило:**
- Пост `X` принимает устройства со статусом `WAITING_X`
- Исключение: `PRE_PRODUCTION` и `KITTING` принимают `WAITING_KITTING`
- `REPAIR` принимает всё

**Ошибки:**
- «Устройство уже прошло этот этап» (текущий индекс > ожидаемый)
- «Устройство не прошло пост X» (текущий индекс < ожидаемый)
- «Устройство в статусе DEFECT» и т.д.

## Batch Limit (`get_batch_limit`)

| Пост | Лимит |
|------|-------|
| WAREHOUSE | 100 |
| VIBROSTAND, FUNC_CONTROL, ОТК, PACKING, ACCOUNTING | 10 |
| PRE_PRODUCTION, ASSEMBLY, REPAIR | 1 |

## Привилегированные роли

Роли, обходящие маршрут (`route_bypass_roles`) и cooldown (`cooldown_bypass_roles`), настраиваются в `pm_system_config`:

```python
get_route_bypass_roles(db)    # для пропуска проверки маршрута
get_cooldown_bypass_roles(db) # для пропуска таймера
```

По умолчанию: `ADMIN, MANAGER, SHOP_MANAGER, ROOT`

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `src/logic/workflow.py` | WorkflowEngine — все проверки |
| `src/system_config.py` | Настройки из pm_system_config |
| `web/api/scan_api.py` | Вызовы WorkflowEngine в process-batch и do_action |
