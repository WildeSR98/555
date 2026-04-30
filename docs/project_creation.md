# Создание проекта — Production Manager

## Обзор

Создание проекта — многошаговый процесс: пользователь заполняет форму в браузере, бэкенд генерирует устройства с серийными номерами и MAC-адресами, назначает маршрутный лист, создаёт структуру папок на сетевом диске и оповещает все вкладки через WebSocket.

---

## 1. UI — Фронтенд

**Файл:** `web/templates/projects.html`

Пользователь нажимает кнопку **➕ Создать** → открывается модальное окно `createModal`.

**Форма собирает:**
- Код проекта, Название (обязательно), Ссылка на спеку, Проверочный код
- Менеджер (выбор из списка, рендерится сервером через Jinja2)
- **Строки устройств** (добавляются динамически через `addDeviceRow()`)

**Каждая строка устройства содержит:**

| Поле | Описание |
|---|---|
| Part Number | Текстовое поле |
| Категория | Dropdown (TIOGA, SERVAL, PC, ...) |
| Модель | Динамически заполняется по категории |
| Количество | Число |
| Режим SN | `Из пула` / `Вручную` — при "вручную" появляется textarea |
| Режим MAC | `Из пула` / `Вручную` — виден только для категорий с MAC |

> При выборе категории JS автоматически выбирает подходящий маршрутный лист (`autoSelectRoute()`).

**Отправка:** функция `submitCreate()` → `POST /api/projects` с JSON-телом.

---

## 2. API — Backend (FastAPI)

**Файл:** `web/api/projects_api.py`, эндпоинт `POST /api/projects/`

**Права доступа:** только `ADMIN`, `MANAGER`, `SHOP_MANAGER`.

### Шаг 1 — Создание записи проекта в БД

```python
new_proj = Project(
    name=..., code=..., spec_link=..., spec_code=...,
    status='PLANNING',   # начальный статус
    manager_id=...,
    created_at=datetime.now()
)
db.add(new_proj)
db.flush()  # получаем ID без commit
```

### Шаг 2 — Генерация устройств и SN (для каждой строки × qty)

**Генерация серийных номеров:**
- Находит последний SN в БД для данной модели по `model_id`
- Инкрементирует счётчик и формирует: `{sn_prefix}{counter:05d}` (напр. `60LXTRDC00042`)
- При `sn_mode='manual'` — берёт из введённых пользователем SN
- Записывает SN в таблицу `tasks_serialnumber` с `is_used=True`

**Создание устройства:**

```python
Device(
    project_id=new_proj.id,
    name=f"{part_number} #{i+1}",
    part_number=...,
    device_type=dm.category,
    serial_number=new_sn_str,
    status='WAITING_KITTING',  # начальный статус
    created_at=datetime.now()
)
```

### Шаг 3 — Назначение MAC-адресов

Зависит от категории устройства:

| Категория | MAC1 (LAN) | MAC2 (BMC) |
|---|---|---|
| `TIOGA`, `SERVAL`, `OCTOPUS` | ✅ | ✅ |
| `PC` | ✅ | ❌ |
| Остальные | ❌ | ❌ |

**Логика `_next_free_mac()`:**
1. Берёт первый свободный MAC из пула (`is_used=False`)
2. Если пул пуст — генерирует новый: `последний MAC в БД + 1`
3. Проверяет на коллизию
4. Помечает как занятый: `is_used=True`, привязывает `device_id` и `project_id`

### Шаг 4 — Назначение маршрутного листа

```
route_config_id указан вручную?
  └─ Да → использует его
  └─ Нет → ищет RouteConfig по device_type первого устройства
       └─ Не найден → берёт дефолтный (is_default=True)
→ Создаёт ProjectRoute(project_id, route_config_id, assigned_by_id)
```

### Шаг 5 — Создание папок на сетевом диске

Вызывается скрипт `scripts/create_project_folders.py` через динамический import (`importlib`).

> **Важно:** ошибка сети не блокирует создание проекта — он будет создан в любом случае.

Структура папок определяется переменными `.env`:

```
NET_PROJECTS_DIR/
  └─ {project_name}/
      ├─ Complectation/   →  stage / PN / SN   (NET_STAGES_FULL)
      ├─ OTK/             →  stage / PN / SN
      ├─ Packing Stand/   →  stage / PN / SN
      ├─ Tests/           →  stage / PN / SN
      ├─ Vibrostand/      →  stage / PN         (NET_STAGES_PN)
      ├─ FRU/             →  пустая папка        (NET_STAGES_EMPTY)
      ├─ Accounting/      →  пустая папка
      └─ Warehouse/       →  пустая папка
```

**Переменные окружения:**

| Переменная | Значение по умолчанию | Описание |
|---|---|---|
| `NET_PROJECTS_DIR` | `\\192.168.106.29\PR_DEP\Assembly` | Корень на сетевом диске |
| `NET_STAGES_FULL` | `Complectation,OTK,Packing Stand,Tests` | Этапы с полной вложенностью PN/SN |
| `NET_STAGES_PN` | `Vibrostand` | Этапы только с PN (без SN) |
| `NET_STAGES_EMPTY` | `FRU,Accounting,Warehouse` | Только папка этапа, без вложений |

### Шаг 6 — Генерация Excel-файла

Если устройства имеют MAC-адреса **и** папки успешно созданы → создаётся файл `{project_name}_mac_sn.xlsx` в корне папки проекта.

Колонки: `PN | SN | MAC1 (LAN) | MAC2 (BMC)`

Формирование через `openpyxl` со стилями (заморозка строки заголовка, чередующиеся строки, моноширинный шрифт).

### Шаг 7 — WebSocket broadcast

```python
await ws_manager.broadcast({
    "type": "project_created",
    "id": new_proj.id,
    "name": new_proj.name,
    "device_count": device_count
})
```

Все открытые вкладки с деревом проектов получают событие и перезагружают дерево автоматически (debounce 1.5 сек).

---

## 3. Модели БД

**Файл:** `src/models.py`

| Таблица | Назначение |
|---|---|
| `tasks_project` | Проект (`code`, `name`, `status=PLANNING`, `spec_link`, ...) |
| `tasks_device` | Устройство (`project_id`, `serial_number`, `status=WAITING_KITTING`, ...) |
| `tasks_serialnumber` | Пул SN — фиксирует каждый выданный серийный номер |
| `pm_mac_address` | Пул MAC — помечает назначенные MAC (`is_used=True`, `device_id`, `project_id`) |
| `pm_project_route` | Связь проект → маршрутный лист |

---

## 4. Полная схема потока

```
[Пользователь] → нажимает "Создать проект"
      ↓
[JS openCreateModal()]
  - загружает список маршрутов (GET /api/route-configs)
  - загружает статистику MAC-пула (GET /api/mac-pool/stats)
      ↓
[JS submitCreate()] → POST /api/projects
      ↓
[projects_api.create_project()]
  1. Проверка прав (ADMIN / MANAGER / SHOP_MANAGER)
  2. INSERT tasks_project (status=PLANNING)
  3. FOR каждое устройство × qty:
       - Генерация / валидация SN → INSERT tasks_serialnumber
       - INSERT tasks_device (status=WAITING_KITTING)
       - Назначение MAC → UPDATE / INSERT pm_mac_address
  4. db.commit()
  5. INSERT pm_project_route (маршрутный лист)
  6. db.commit()
  7. scripts/create_project_folders.py → папки на сетевом диске
  8. scripts/create_project_excel() → Excel с MAC / SN
  9. WebSocket broadcast("project_created")
 10. Ответ: { ok, message, net_folders, mac_warnings }
      ↓
[JS] → закрывает модалку, вызывает loadTree()
  → дерево обновляется у всех пользователей одновременно
```

---

## 5. Обработка ошибок

| Ситуация | Поведение |
|---|---|
| Дублирующий код проекта | HTTP 400: «Проект с кодом X уже существует» |
| Нет прав | HTTP 403 |
| MAC-пул пуст | Проект создаётся, в ответе `mac_warnings` со списком предупреждений |
| Сеть недоступна | Проект создаётся, папки не создаются, `net_message` сообщает об ошибке |
| Любая другая ошибка БД | `db.rollback()`, HTTP 500 |
