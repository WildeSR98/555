# Управление проектами (Projects)

## Назначение
CRUD проектов, привязка устройств, управление MAC-адресами, импорт/экспорт.

## Структура проекта

```
Проект (pm_projects)
├── Устройства (pm_devices)
│   ├── Серийные номера (pm_serial_numbers)
│   └── MAC-адреса (pm_mac_addresses)
├── Маршрут проекта (pm_project_route_stage)
└── Назначенный маршрут (pm_project_routes → pm_route_configs)
```

## API Endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/projects/tree` | Дерево проектов с вложенными устройствами |
| POST | `/api/projects/` | Создать проект |
| PUT | `/api/projects/{id}` | Обновить проект |
| DELETE | `/api/projects/{id}` | Удалить проект (только ADMIN) |
| GET | `/api/projects/device/{device_id}` | Детали устройства |

## Создание проекта

```
POST /api/projects/
  Body: { name, code, description, quantity, device_type, spec_link, spec_code }
  → Создаёт проект
  → Генерирует N устройств с автоматическими SN (из пула или sequence)
  → Назначает MAC-адреса (из пула pm_mac_addresses)
  → WS broadcast: project_created
```

## Удаление проекта

**Доступно только ADMIN.** Порядок удаления (из-за FK constraints):

1. `WorkLog` — записи истории
2. `ProjectRouteStage` — маршруты проекта
3. `ProjectRoute` — назначенный маршрут
4. `MacAddress` — освобождение MAC-адресов (is_used = False)
5. `SerialNumber` — серийные номера устройств
6. `Device` — устройства
7. `Project` — сам проект

## MAC-адреса

При создании устройства автоматически назначается MAC-адрес из пула:
- **DUAL_MAC_CATEGORIES** — устройства с двумя MAC (ETH + Wi-Fi)
- **SINGLE_MAC_CATEGORIES** — один MAC
- Если пул пуст → генерация нового = последний MAC + 1

## Спецификация проекта

Опциональные поля:
- `spec_link` — ссылка на документ спецификации
- `spec_code` — проверочный код (4-6 цифр)

Если заданы → при первом сканировании SN из этого проекта требуется верификация.

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/projects_api.py` | CRUD проектов, создание устройств, MAC |
| `web/templates/projects.html` | UI дерева проектов |
| `src/models.py` | ORM: Project, Device, SerialNumber, MacAddress |
