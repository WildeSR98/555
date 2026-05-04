# Таймер этапа (Stage Timer)

## Назначение
Таймер определяет **минимальное время работы** на этапе производства. Пока таймер не истёк, кнопки «Готово / Брак» заблокированы. Это предотвращает поспешное закрытие этапа без реального выполнения работы.

## Источник значения таймера (приоритет)

| Приоритет | Источник | Таблица | Когда используется |
|-----------|----------|---------|--------------------|
| 1 (высший) | Маршрут проекта | `pm_project_route_stage` | Если есть записи для `project_id + device_type` |
| 2 | Глобальный маршрут | `pm_route_config_stage` | Если проектного маршрута нет, по `device_type` или `is_default=True` |
| 3 (fallback) | Хардкод | — | `300` секунд (5 минут) |

**Функция:** `_get_stage_timer()` в `web/api/scan_api.py`

## Нормализация ключей

Между `workplace_type` (тип рабочего поста) и `stage_key` (ключ этапа маршрута) существует несовпадение:

| Workplace type | Route stage key |
|----------------|-----------------|
| `PRE_PRODUCTION` | `KITTING` |
| Все остальные | совпадают |

Нормализация выполняется в `_get_stage_timer()` через маппинг `_WP_TO_ROUTE`.

## Полный flow

### 1. Запуск таймера (scan_in)

```
Пользователь сканирует SN → process-batch → action(scan_in)
  → scan_api.do_action():
    → _get_stage_timer(db, device, workplace_type)
      → ProjectRouteStage? → RouteConfig? → 300
    → response: {stage_timer_seconds: N}
  → scan.html:
    → state.stageTimerSeconds = N
    → startStageTimer(N)
    → lockActionButtons() — кнопки заблокированы
```

### 2. Обратный отсчёт (фронтенд)

```
setInterval (каждую секунду):
  → _timerLeft--
  → _updateTimerDisplay() — обновляет SVG-кольцо + MM:SS
  → если _timerLeft <= 0:
    → stopStageTimer(done=true)
    → unlockActionButtons() — кнопки разблокированы
    → pulse-анимация на кнопке «Готово»
```

### 3. Серверная проверка (cooldown)

```
Пользователь нажимает «Готово» → action(complete)
  → scan_api.do_action():
    → cooldown_sec = _get_stage_timer(db, device, old_status)
    → WorkflowEngine.can_change_status(cooldown_seconds=cooldown_sec)
      → если time_passed < cooldown_sec:
        → return {ok: false, error: "Ожидайте таймер. Осталось M:SS"}
      → иначе: разрешить переход
```

### 4. Обновление через WebSocket (realtime)

```
Админ меняет таймер в маршруте проекта:
  → PUT /api/project-routes/{id}/device/{type}
    → project_routes_api.save_project_device_route()
      → ws_manager.broadcast({
          type: "project_route_saved",
          project_id, device_type,
          stages: {KITTING: 600, PRE_PRODUCTION: 600, ASSEMBLY: 300, ...}
        })
  → scan.html:
    → ws:project_route_saved event
    → _handleTimerWsUpdate(detail):
      → фильтр по project_id (только устройства из этого проекта)
      → фильтр по workplaceType (только текущий этап)
      → пересчёт remaining = newTimer - elapsed
      → startStageTimer(newTimer, remaining)
```

### 5. Восстановление после перезагрузки страницы

```
Страница перезагружена:
  → restoreState() — из sessionStorage
  → _restoreTimerFromServer():
    → GET /api/scan/device-timer?device_id=X&stage_key=Y
      → _get_stage_timer(db, device, stage_key)
    → remaining = timerSeconds - elapsed (от timerStartedAt)
    → startStageTimer(timerSeconds, remaining)
```

## Визуальное отображение

- **SVG-кольцо** с обратным отсчётом (radius=30, circumference=188.5)
- **Цвета:** фиолетовый (>30с) → жёлтый (≤30с) → зелёный (0с)
- **Блокировка кнопок:** opacity 0.4, cursor not-allowed, title "Ожидайте окончания таймера"
- **По истечении:** pulse-анимация на кнопке «Готово»

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/scan_api.py` | `_get_stage_timer()`, `device-timer` endpoint, cooldown в `do_action` |
| `web/api/project_routes_api.py` | WS broadcast `project_route_saved` с таймерами |
| `web/api/route_config_api.py` | WS broadcast `route_saved` с таймерами |
| `web/templates/scan.html` | Таймер UI, `startStageTimer()`, `_handleTimerWsUpdate()` |
| `src/logic/workflow.py` | `WorkflowEngine.can_change_status()` — серверный cooldown |
