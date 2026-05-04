# Маршрутные листы (Route Configuration)

## Назначение
Маршрутные листы определяют порядок этапов производства и настройки каждого этапа (включён/выключен, таймер). Существуют два уровня: **глобальные маршруты** и **маршруты проектов**.

## Уровни маршрутов

### 1. Глобальный маршрут (`pm_route_config` + `pm_route_config_stage`)

- Привязан к `device_type` (типу устройства) или является `is_default=True`
- Используется как шаблон, если у проекта нет индивидуального маршрута
- Управляется через страницу «Маршрутные листы» (`/route-configs`)

### 2. Маршрут проекта (`pm_project_route_stage`)

- Привязан к `project_id + device_type`
- Переопределяет глобальный маршрут для конкретного проекта
- Управляется через вкладку «Проекты» на странице маршрутных листов

## Этапы конвейера (Pipeline Stages)

```
KITTING → ASSEMBLY → VIBROSTAND → TECH_CONTROL_1_1 → TECH_CONTROL_1_2
→ FUNC_CONTROL → TECH_CONTROL_2_1 → TECH_CONTROL_2_2
→ PACKING → ACCOUNTING → WAREHOUSE → QC_PASSED
```

Каждый этап имеет:
- `stage_key` — уникальный ключ (напр. `KITTING`)
- `is_enabled` — включён/выключен
- `order_index` — порядок
- `timer_seconds` — таймер минимального времени работы (default: 300)
- `label` — отображаемое название (опционально)

## API Endpoints

### Глобальные маршруты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/route-configs` | Список всех маршрутов |
| POST | `/api/route-configs` | Создать маршрут |
| GET | `/api/route-configs/{id}` | Детали маршрута |
| PUT | `/api/route-configs/{id}` | Обновить маршрут + WS broadcast |
| DELETE | `/api/route-configs/{id}` | Удалить (кроме default) |
| PUT | `/api/route-configs/project/{project_id}` | Назначить маршрут проекту |

### Маршруты проектов

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/project-routes/projects` | Список проектов с типами устройств |
| GET | `/api/project-routes/{project_id}/device/{type}` | Этапы маршрута |
| PUT | `/api/project-routes/{project_id}/device/{type}` | Сохранить + WS broadcast |
| DELETE | `/api/project-routes/{project_id}/device/{type}` | Сбросить до глобального |
| GET | `/api/project-routes/{project_id}/device/{type}/check-remove` | Проверка зависших устройств |

## Пропуск отключённых этапов

При завершении этапа (`complete`) вызывается `resolve_next_status()`:

```python
# Пример: ASSEMBLY завершён, VIBROSTAND отключён
# resolve_next_status('ASSEMBLY', ['KITTING', 'ASSEMBLY', 'TECH_CONTROL_1_1', ...])
# → 'WAITING_TECH_CONTROL_1_1' (VIBROSTAND пропущен)
```

## Автоматический перевод устройств при изменении маршрута

Когда этап **удаляется** из маршрута проекта, устройства на этом этапе автоматически переводятся на следующий активный этап:

```python
_advance_stranded_devices(project_id, device_type, enabled_keys, db)
# → device.status = WAITING_NEXT_ACTIVE_STAGE
# → WorkLog: ROUTE_CHANGE
```

## WS Broadcast

При сохранении маршрута отправляется WS-событие:

```json
{
  "type": "project_route_saved",
  "project_id": 35,
  "project_name": "Проект X",
  "device_type": "SERVAL",
  "stages": {
    "KITTING": 600,
    "PRE_PRODUCTION": 600,
    "ASSEMBLY": 300,
    "VIBROSTAND": 300
  }
}
```

> **Alias:** `KITTING` дублируется как `PRE_PRODUCTION` в stages dict, т.к. фронтенд использует `workplace_type` (PRE_PRODUCTION), а маршрут — `stage_key` (KITTING).

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/route_config_api.py` | CRUD глобальных маршрутов |
| `web/api/project_routes_api.py` | CRUD маршрутов проектов, автоперевод устройств |
| `web/templates/route_configs.html` | UI маршрутных листов |
| `src/models.py` | ORM-модели: `RouteConfig`, `RouteConfigStage`, `ProjectRouteStage` |
