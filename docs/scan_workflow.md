# Сканирование (Scan Workflow)

## Назначение
Основной производственный процесс: сканирование серийных номеров устройств на рабочих постах, приём в работу, завершение этапа, передача в брак.

## Этапы workflow

### 1. Выбор рабочего места (start-session)

```
POST /api/scan/start-session
  Body: { workplace_id }
  → Работник = текущий авторизованный пользователь (из cookie-сессии)
  → Создаёт или переиспользует WorkSession
  → Возвращает: session_id, worker_id, workplace_type, batch_limit, stage_timer_seconds
```

**Batch limit** зависит от типа поста:
- Склад (`WAREHOUSE`): 100
- Вибростенд, ОТК, Упаковка и т.д.: 10
- Комплектовка, Сборка, Ремонт: 1

### 2. Сканирование SN (process-batch)

```
POST /api/scan/process-batch
  Body: { session_id, workplace_id, worker_id, serial_numbers, verified_project_ids }
  → Валидация: существует ли устройство, правильный ли пост
  → Проверка спецификации (require_spec)
  → Возвращает: devices[{id, sn, status, project_id, need_scan_in}]
```

**Логика валидации:**
1. Поиск устройства по SN
2. Проверка: может ли пост принять устройство (`WorkflowEngine.can_accept_device`)
3. Проверка спецификации проекта (если `project.spec_code` задан и проект не верифицирован)
4. Определение: нужен `scan_in` или устройство уже принято

### 3. Принятие в работу (action: scan_in)

```
POST /api/scan/action
  Body: { action: "scan_in", device_ids, ... }
  → device.status = workplace_type (напр. ASSEMBLY)
  → device.current_worker_id = worker_id
  → WorkLog: SCAN_IN
  → WS broadcast: device_status_changed
  → Возвращает: stage_timer_seconds (из маршрута проекта)
```

### 4. Завершение этапа (action: complete)

```
POST /api/scan/action
  Body: { action: "complete", device_ids, ... }
  → Определение следующего статуса:
    1. Проектный маршрут (ProjectRouteStage) — какие этапы включены
    2. Глобальный маршрут (RouteConfig)
    3. resolve_next_status() — пропуск отключённых этапов
  → Проверка cooldown (таймер из маршрута)
  → device.status = WAITING_NEXT_STAGE
  → WorkLog: COMPLETED
  → WS broadcast: device_status_changed
```

### 5. Передача в брак (action: defect)

```
POST /api/scan/action
  Body: { action: "defect", device_ids, notes: "причина" }
  → device.status = DEFECT
  → WorkLog: DEFECT
  → WS broadcast: device_status_changed
  → Комментарий обязателен
```

### 6. Полуфабрикат (action: semifinished)

```
POST /api/scan/action
  Body: { action: "semifinished", device_ids }
  → device.is_semifinished = True
  → WorkLog: MAKE_SEMIFINISHED
```

### 7. Завершение смены (end-session)

```
POST /api/scan/end-session
  Body: { session_id }
  → session.is_active = False
  → session.ended_at = now()
```

## Фазы на фронтенде

| Фаза | Кнопки | Когда |
|------|--------|-------|
| `accept` | «Принять в работу» | Устройство отсканировано, нужен scan_in |
| `action` | «Готово», «Брак», «Полуфабрикат» | Устройство принято, можно завершать |

## Auto-advance посты

На этих постах после scan_in устройство **остаётся в буфере** и сразу доступны кнопки действий (без повторного сканирования):

`PRE_PRODUCTION, ASSEMBLY, VIBROSTAND, TECH_CONTROL_1_1/1_2, FUNC_CONTROL, TECH_CONTROL_2_1/2_2, PACKING, ACCOUNTING, WAREHOUSE, REPAIR`

## Пост Ремонта (REPAIR)

Особая логика: при «Готово» открывается модальное окно с:
- Обязательным комментарием (описание ремонта)
- Выбором целевого статуса (на какой этап вернуть устройство)

## Проверка спецификации (Spec Verification)

Если у проекта задан `spec_code`:
1. При первом сканировании SN из этого проекта → модалка «Проверьте спецификацию»
2. Пользователь открывает ссылку на спецификацию
3. Вводит проверочный код
4. Если код верный → `project_id` добавляется в `verifiedProjectIds`
5. Повторное сканирование проходит без проверки

## Автозавершение смены

Каждую минуту проверяется время. Если 05:00–05:05 → автоматическое завершение смены.

## Состояние (State Management)

Состояние хранится в `sessionStorage` (ключ `scan_session_state`):
```
{
  sessionId, workerId, workplaceId, workplaceType, batchLimit,
  devices, phase, verifiedProjectIds,
  workerName, workplaceName, lastFeedback,
  stageTimerSeconds, timerStartedAt, currentProjectId
}
```

Восстанавливается при перезагрузке страницы.

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/scan_api.py` | Все API endpoints сканирования |
| `web/templates/scan.html` | UI сканирования, буфер, таймер, WS |
| `src/logic/workflow.py` | `WorkflowEngine` — валидация переходов, cooldown |
