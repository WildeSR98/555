# WebSocket (Realtime Events)

## Назначение
WebSocket обеспечивает realtime-обновления на всех открытых страницах приложения: уведомления о действиях, обновление таймеров, синхронизация данных.

## Архитектура

### Серверная часть

**Синглтон менеджер:** `web/ws_manager.py`

```python
class ConnectionManager:
    active: list[WebSocket]
    connect(ws)     # accept + добавить
    disconnect(ws)  # удалить
    broadcast(msg)  # отправить всем, удалить мёртвые соединения
```

**WS Endpoint:** `web/api/ws_api.py`

```
WebSocket /ws
  → Авторизация через Starlette session (user_id)
  → Не авторизован → close(1008 Policy Violation)
  → Подключён → manager.connect()
  → Цикл: receive_json → ping/pong
  → Отключение → manager.disconnect()
```

### Клиентская часть (base.html)

```javascript
// Подключение с автоматическим переподключением (3 сек)
ws = new WebSocket('ws://host/ws')

// Ping каждые 25 сек (keep-alive)
setInterval(() => ws.send({type: 'ping'}), 25000)

// Диспетчеризация событий через CustomEvent
WS_EVENTS = {
    'device_status_changed': 'ws:device_changed',
    'project_created':       'ws:project_created',
    'project_deleted':       'ws:project_deleted',
    'route_saved':           'ws:route_saved',
    'project_route_saved':   'ws:project_route_saved',
    'sn_pool_updated':       'ws:sn_pool_updated',
}
// window.dispatchEvent(new CustomEvent(evtName, {detail: evt}))
```

## Типы событий

### device_status_changed
Отправляется при любом изменении статуса устройства (scan_in, complete, defect).

```json
{
  "type": "device_status_changed",
  "device_id": 114,
  "device_name": "Устройство X",
  "serial_number": "SN001",
  "project_id": 35,
  "project_name": "Проект Y",
  "old_status": "ASSEMBLY",
  "new_status": "WAITING_VIBROSTAND",
  "old_status_display": "Сборка",
  "new_status_display": "Ожидание вибростенда",
  "action": "COMPLETED",
  "worker": "Иванов И.И.",
  "timestamp": "04.05.2026 14:30"
}
```

**Слушатели:** dashboard, projects, scan (toast-уведомления)

### project_route_saved
Отправляется при сохранении маршрута проекта.

```json
{
  "type": "project_route_saved",
  "project_id": 35,
  "project_name": "Проект Y",
  "device_type": "SERVAL",
  "stages": {"KITTING": 600, "PRE_PRODUCTION": 600, "ASSEMBLY": 300}
}
```

**Слушатели:**
- `scan.html` — обновляет таймер (фильтр по project_id + workplaceType)
- `route_configs.html` — обновляет список

### route_saved
Отправляется при сохранении глобального маршрута.

```json
{
  "type": "route_saved",
  "id": 1,
  "route_name": "Маршрут SERVAL",
  "stages": {"KITTING": 600, "PRE_PRODUCTION": 600, "ASSEMBLY": 300}
}
```

**Слушатели:** `scan.html` — обновляет таймер, `route_configs.html`

### project_created / project_deleted
Отправляются при создании/удалении проекта.

### sn_pool_updated
Отправляется при изменении пула серийных номеров.

### admin_broadcast
Широковещательное сообщение от администратора (объявление).

## Toast-уведомления

- **device_status_changed:** группируемый toast (одинаковые worker+status объединяются, счётчик ×N)
- **project_route_saved:** простой toast «📋 Маршрут проекта»
- **admin_broadcast:** заметный toast (10 сек, жёлтая рамка)
- Переключение уведомлений: кнопка 🔔/🔕 в sidebar

## Индикатор подключения

В sidebar отображается LIVE-индикатор:
- 🟢 Зелёный пульс — подключено
- 🟡 Жёлтый — подключение
- 🔴 Красный — отключено

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/ws_manager.py` | ConnectionManager — синглтон менеджер |
| `web/api/ws_api.py` | WebSocket endpoint `/ws` |
| `web/templates/base.html` | WS подключение, диспетчеризация, toast |
| `web/templates/scan.html` | Обработчики `ws:route_saved`, `ws:project_route_saved` |
