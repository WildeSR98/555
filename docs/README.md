# Production Manager

Система управления производственным процессом — контроль устройств от комплектовки до отгрузки со склада.

Два интерфейса: **веб** (FastAPI) и **десктоп** (PyQt6). Оба работают с одной базой данных.

---

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура)
- [Структура проекта](#структура-проекта)
- [База данных](#база-данных)
- [Производственный конвейер](#производственный-конвейер)
- [Веб-интерфейс](#веб-интерфейс)
- [Десктоп-приложение](#десктоп-приложение)
- [API-справочник](#api-справочник)
- [Роли и права](#роли-и-права)
- [Конфигурация](#конфигурация)
- [Docker и PostgreSQL](#docker-и-postgresql)
- [Сборка и деплой](#сборка-и-деплой)
- [Git-процесс](#git-процесс)

---

## Быстрый старт

### Требования

- Python 3.10+
- PostgreSQL 16 (через Docker) или SQLite (для разработки)

### Установка

```bash
# 1. Клонировать
git clone https://github.com/WildeSR98/555.git
cd 555

# 2. Создать виртуальное окружение
python -m venv .venv

# Windows
.venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env (скопировать шаблон)
copy .env.example .env
```

### Запуск веб-сервера

> **Важно:** Все команды `python` выполняются из активированного виртуального окружения.  
> Если venv не активирован, используйте `.venv\Scripts\python.exe` вместо `python`.

```powershell
# Активировать venv (один раз за сессию терминала)
.venv\Scripts\activate

# Запустить сервер (разработка)
python -m uvicorn web.main:app --host 127.0.0.1 --port 8000 --reload
```

Или через PowerShell-скрипт:

```powershell
.\run_web.ps1 -Reload
```

Веб-интерфейс: **http://127.0.0.1:8000**  
Документация API: **http://127.0.0.1:8000/docs**

### Запуск десктоп-приложения

```bash
python src/main.py
```

### Создание root-пользователя

```bash
python create_root.py
```

---

## Архитектура

```
┌─────────────────────────────────────────────┐
│              Пользователи                   │
│    Веб-браузер    │    Десктоп (PyQt6)       │
└────────┬──────────┴────────────┬────────────┘
         │                       │
┌────────▼──────────┐ ┌─────────▼────────────┐
│   FastAPI (web/)  │ │   PyQt6 GUI (src/ui/) │
│   ├─ routes/      │ │   ├─ main_window     │
│   ├─ api/         │ │   ├─ scan_tab        │
│   ├─ templates/   │ │   ├─ projects_tab    │
│   └─ static/      │ │   └─ pipeline_tab    │
└────────┬──────────┘ └─────────┬────────────┘
         │                       │
┌────────▼───────────────────────▼────────────┐
│          Общий слой (src/)                   │
│   ├─ models.py     — ORM-модели              │
│   ├─ database.py   — подключение к БД        │
│   ├─ config.py     — конфигурация (.env)      │
│   ├─ logic/        — бизнес-логика           │
│   │   └─ workflow.py — переходы состояний    │
│   └─ logger.py     — логирование             │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│      PostgreSQL / SQLite                     │
│   ├─ accounts_user       (пользователи)      │
│   ├─ tasks_project       (проекты)           │
│   ├─ tasks_device        (устройства)        │
│   ├─ tasks_operation     (операции)           │
│   ├─ production_workplace (рабочие места)    │
│   ├─ production_worklog  (журнал действий)   │
│   ├─ pm_route_config     (маршруты)          │
│   ├─ pm_mac_address      (пул MAC-адресов)   │
│   └─ pm_device_category  (категории)         │
└─────────────────────────────────────────────┘
```

---

## Структура проекта

```
appwin/
├── src/                          # Общее ядро (модели, БД, логика)
│   ├── config.py                 # Конфигурация из .env
│   ├── database.py               # SQLAlchemy engine, сессии
│   ├── models.py                 # Все ORM-модели
│   ├── logger.py                 # Настройка логирования
│   ├── system_config.py          # Key-value системные настройки
│   ├── main.py                   # Точка входа десктоп-приложения
│   ├── logic/
│   │   └── workflow.py           # Машина состояний конвейера
│   └── ui/                       # Десктоп GUI (PyQt6)
│       ├── main_window.py        # Главное окно с вкладками
│       ├── login_dialog.py       # Окно авторизации
│       ├── scan_tab.py           # Вкладка «Сканирование»
│       ├── projects_tab.py       # Вкладка «Проекты»
│       ├── pipeline_tab.py       # Вкладка «Конвейер»
│       ├── analytics_tab.py      # Вкладка «Аналитика»
│       ├── admin_tab.py          # Вкладка «Администрирование»
│       ├── sn_pool_tab.py        # Вкладка «Пул серийных номеров»
│       ├── dashboard_tab.py      # Вкладка «Дашборд»
│       ├── device_status_tab.py  # Вкладка «Статус устройства»
│       ├── styles.py             # Стили Qt (QSS)
│       └── widgets/              # Кастомные виджеты
│
├── web/                          # Веб-интерфейс (FastAPI)
│   ├── main.py                   # Точка входа FastAPI
│   ├── dependencies.py           # Auth middleware, CSRF, роли
│   ├── ws_manager.py             # WebSocket менеджер
│   ├── routes/                   # HTML-страницы (Jinja2)
│   │   ├── auth.py               # /login, /logout
│   │   ├── dashboard.py          # /dashboard
│   │   ├── projects.py           # /projects
│   │   ├── pipeline.py           # /pipeline
│   │   ├── scan.py               # /scan
│   │   ├── analytics.py          # /analytics
│   │   ├── admin.py              # /admin
│   │   ├── devices.py            # /devices
│   │   ├── sn_pool.py            # /sn-pool
│   │   ├── route_configs.py      # /route-configs
│   │   └── archive.py            # /archive
│   ├── api/                      # JSON API
│   │   ├── dashboard_api.py      # /api/dashboard
│   │   ├── projects_api.py       # /api/projects
│   │   ├── pipeline_api.py       # /api/pipeline
│   │   ├── scan_api.py           # /api/scan
│   │   ├── analytics_api.py      # /api/analytics
│   │   ├── admin_api.py          # /api/admin
│   │   ├── devices_api.py        # /api/devices
│   │   ├── sn_pool_api.py        # /api/sn-pool
│   │   ├── mac_pool_api.py       # /api/mac-pool
│   │   ├── route_config_api.py   # /api/route-configs
│   │   ├── project_routes_api.py # /api/project-routes
│   │   ├── archive_api.py        # /api/archive
│   │   ├── health_api.py         # /api/health
│   │   └── ws_api.py             # WebSocket /ws
│   ├── templates/                # Jinja2 HTML-шаблоны
│   └── static/                   # CSS, JS, изображения
│
├── scripts/                      # Утилиты
│   ├── create_project_folders.py # Создание папок проекта на сетевом диске
│   └── sync_images_to_network.py # Синхронизация фото на сетевой диск
│
├── .agents/skills/               # AI-агентские скиллы
│   ├── git-workflow/             # Правила работы с Git
│   ├── karpathy-guidelines/      # Принципы качественного кода
│   └── db-rollback/              # Откат изменений БД
│
├── .env                          # Конфигурация (не в git)
├── .env.example                  # Шаблон конфигурации
├── docker-compose.yml            # PostgreSQL в Docker
├── requirements.txt              # Python зависимости
├── create_root.py                # Создание root-пользователя
├── build.py                      # Сборка .exe (PyInstaller)
├── run_web.ps1                   # Запуск веб-сервера (PowerShell)
└── CHANGELOG.md                  # История изменений
```

---

## База данных

Проект поддерживает два движка:

| Движок | Когда использовать |
|---|---|
| **SQLite** | Локальная разработка, тестирование |
| **PostgreSQL** | Продакшн, многопользовательская работа |

Переключение через `.env`:

```env
# SQLite (по умолчанию)
DB_TYPE=sqlite
DB_PATH=db.sqlite3

# PostgreSQL
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=production_db
DB_USER=prod_user
DB_PASSWORD=your_password
```

### Основные таблицы

| Таблица | Описание |
|---|---|
| `accounts_user` | Пользователи системы (роли, пароли, пин-коды) |
| `auth_group` | Группы (Django-совместимые) |
| `tasks_project` | Проекты (код, название, менеджер, дедлайн) |
| `tasks_device` | Устройства (SN, PN, тип, статус, текущий работник) |
| `tasks_operation` | Операции над устройствами |
| `tasks_devicemodel` | Модели устройств для генерации SN |
| `tasks_serialnumber` | Пул серийных номеров |
| `production_workplace` | Рабочие места (тип, пул, ограничения) |
| `production_worksession` | Сессии работников |
| `production_worklog` | Журнал действий (scan_in, completed, defect...) |
| `pm_route_config` | Конфигурации маршрутов |
| `pm_route_config_stage` | Этапы маршрута (вкл/выкл, порядок, таймер) |
| `pm_project_route_stage` | Индивидуальные маршруты проекта |
| `pm_mac_address` | Пул MAC-адресов |
| `pm_device_category` | Категории устройств |
| `pm_system_config` | Системные настройки (key-value) |

### Миграции

Миграции выполняются скриптами в корне проекта:

```bash
python migrate_to_postgres.py         # SQLite → PostgreSQL
python migrate_sqlite_to_pg.py        # Альтернативный перенос
python migrate_device_categories.py   # Сидирование категорий
python migrate_mac_pool.py            # Миграция MAC-пула
python migrate_route_stage_label.py   # Добавление label к этапам
```

---

## Производственный конвейер

Устройство проходит этапы в строгом порядке. Каждый этап — это рабочее место (`Workplace`), на которое работник сканирует устройство.

### Этапы (по умолчанию)

```
Комплектовка → Сборка → Вибростенд → ОТК 1.1 → ОТК 1.2 →
→ Функц. контроль → ОТК 2.1 → ОТК 2.2 →
→ Упаковка → Учёт → Склад
```

### Статусы устройства

Каждый этап имеет пару: `WAITING_X` (ожидание) и `X` (в работе).

| Статус | Описание |
|---|---|
| `WAITING_KITTING` | Ожидание комплектовки |
| `PRE_PRODUCTION` | Комплектовка |
| `WAITING_ASSEMBLY` | Ожидание сборки |
| `ASSEMBLY` | Сборка |
| `WAITING_VIBROSTAND` | Ожидание вибростенда |
| `VIBROSTAND` | Вибростенд |
| `WAITING_TECH_CONTROL_1_1` | Ожидание ОТК 1.1 |
| `TECH_CONTROL_1_1` | Тех. контроль 1.1 |
| ... | ... |
| `WAREHOUSE` | Склад |
| `QC_PASSED` | Контроль пройден (финальный) |
| `DEFECT` | Брак |
| `WAITING_PARTS` | Ожидание запчастей |
| `REPAIR` | Ремонт (возврат на любой этап) |

### Машина состояний (workflow.py)

- Переходы между статусами контролируются таблицей `STRICT_TRANSITIONS`
- Привилегированные роли (ADMIN, MANAGER, ROOT) обходят ограничения
- Кулдаун 5 минут между действиями для рядовых работников
- Ремонт и Брак доступны с любого этапа

### Маршрутные листы

Администратор может настроить маршруты:
- **Глобальные** — привязаны к типу устройства (TIOGA, SERVAL и т.д.)
- **Проектные** — переопределяют глобальный маршрут для конкретного проекта
- Каждый этап можно включить/выключить, переименовать, задать таймер
- Поддержка кастомных этапов (`CUSTOM::Название`)

---

## Веб-интерфейс

### Страницы

| URL | Описание | Доступ |
|---|---|---|
| `/login` | Авторизация | Все |
| `/dashboard` | Дашборд (сводка) | Авторизованные |
| `/projects` | Управление проектами | Авторизованные |
| `/pipeline` | Визуализация конвейера | Авторизованные |
| `/scan` | Сканирование устройств | Авторизованные |
| `/devices` | Поиск устройства по SN | Авторизованные |
| `/sn-pool` | Пул серийных номеров | Авторизованные |
| `/analytics` | Аналитика и графики | Авторизованные |
| `/route-configs` | Маршрутные листы | Авторизованные |
| `/archive` | Архив проектов | Авторизованные |
| `/admin` | Управление пользователями | ADMIN, ROOT |

### Технологии веб-части

- **Backend:** FastAPI + SQLAlchemy + Jinja2
- **Frontend:** Vanilla HTML/CSS/JS (без фреймворков)
- **Авторизация:** Сессии (cookie-based) + CSRF-защита
- **Реалтайм:** WebSocket для живых обновлений
- **Отчёты:** Excel-экспорт через openpyxl

---

## Десктоп-приложение

PyQt6-приложение с идентичной функциональностью. Запускается как `.exe` (сборка через PyInstaller) или через Python.

### Вкладки

| Вкладка | Модуль | Описание |
|---|---|---|
| Дашборд | `dashboard_tab.py` | Сводная информация |
| Сканирование | `scan_tab.py` | Приём/выдача устройств на рабочих местах |
| Проекты | `projects_tab.py` | CRUD проектов, генерация SN |
| Конвейер | `pipeline_tab.py` | Визуализация потока устройств |
| Аналитика | `analytics_tab.py` | Графики, статистика |
| SN Pool | `sn_pool_tab.py` | Управление серийными номерами |
| Администрирование | `admin_tab.py` | Управление пользователями |

### Сборка в .exe

```bash
python build.py
# Результат: dist/ProductionManager.exe
```

---

## API-справочник

Все API-эндпоинты доступны по адресу `/docs` (Swagger UI).

### Аутентификация

Все API-запросы (кроме `/api/health`) требуют авторизованной сессии. Сессия создаётся после входа через `/login`.

### Основные группы

| Группа | Prefix | Описание |
|---|---|---|
| Dashboard | `/api/dashboard` | Сводные данные |
| Projects | `/api/projects` | CRUD проектов, создание устройств, MAC-назначение |
| Pipeline | `/api/pipeline` | Состояние конвейера |
| Scan | `/api/scan` | Сканирование устройств (scan_in, complete, defect) |
| Devices | `/api/devices` | Поиск устройств, история |
| SN Pool | `/api/sn-pool` | Серийные номера, модели, категории |
| MAC Pool | `/api/mac-pool` | Импорт/экспорт MAC-адресов |
| Analytics | `/api/analytics` | Данные для графиков |
| Admin | `/api/admin` | Пользователи (только ADMIN/ROOT) |
| Routes | `/api/route-configs` | Маршрутные листы |
| Project Routes | `/api/project-routes` | Маршруты проектов |
| Archive | `/api/archive` | Архивация проектов |
| Health | `/api/health` | Проверка состояния (без авторизации) |
| WebSocket | `/ws` | Живые обновления |

### Ключевые эндпоинты

```
POST  /api/scan/scan-in         — Взять устройство в работу
POST  /api/scan/complete         — Завершить работу над устройством  
POST  /api/scan/defect           — Отправить в брак

POST  /api/projects/create       — Создать проект с устройствами
GET   /api/projects/list         — Список проектов

POST  /api/admin/users           — Создать пользователя (ADMIN/ROOT)
GET   /api/admin/users           — Список пользователей

GET   /api/health/               — Проверка БД и диска
```

---

## Роли и права

| Роль | Константа | Права |
|---|---|---|
| **ROOT** | `User.ROLE_ROOT` | Полный доступ. Скрыт из UI. Обходит все ограничения |
| **ADMIN** | `User.ROLE_ADMIN` | Управление пользователями, маршрутами, системными настройками |
| **MANAGER** | `User.ROLE_MANAGER` | Управление проектами, просмотр аналитики |
| **SHOP_MANAGER** | `User.ROLE_SHOP_MANAGER` | Начальник цеха — менеджерские права на производстве |
| **EMPLOYEE** | `User.ROLE_EMPLOYEE` | Сотрудник — базовый доступ |
| **WORKER** | `User.ROLE_WORKER` | Работник производства — сканирование устройств |

### Матрица доступа

| Действие | ROOT | ADMIN | MANAGER | SHOP_MGR | EMPLOYEE | WORKER |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Создание пользователей | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Управление маршрутами | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Создание проектов | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Сканирование устройств | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Обход кулдауна | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Обход маршрута | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |

---

## Конфигурация

Все настройки читаются из файла `.env` в корне проекта.

### Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DB_TYPE` | `sqlite` | Тип БД: `sqlite` или `postgresql` |
| `DB_PATH` | `db.sqlite3` | Путь к файлу SQLite |
| `DB_HOST` | `localhost` | Хост PostgreSQL |
| `DB_PORT` | `5432` | Порт PostgreSQL |
| `DB_NAME` | `production_db` | Имя базы данных |
| `DB_USER` | — | Пользователь БД |
| `DB_PASSWORD` | — | Пароль БД |
| `DB_SSLMODE` | `disable` | Режим SSL |
| `SECRET_KEY` | `development-default-key` | Секрет для сессий |
| `CSRF_SECRET` | (из SECRET_KEY) | Секрет для CSRF-токенов |
| `DEBUG` | `False` | Режим отладки (SQL-логи) |

---

## Docker и PostgreSQL

### Запуск PostgreSQL

```bash
docker-compose up -d
```

Контейнер `production_postgres` поднимает PostgreSQL 16 на порту `5432`.

### Восстановление дампа

```bash
# Скопировать дамп в контейнер
docker cp dump.sql production_postgres:/tmp/dump.sql

# Восстановить
docker exec -i production_postgres psql -U prod_user -d production_db -f /tmp/dump.sql
```

### Подключение к БД

```bash
docker exec -it production_postgres psql -U prod_user -d production_db
```

---

## Сборка и деплой

### Сборка десктоп-приложения

```bash
python build.py
```

Результат: `dist/ProductionManager.exe` — один файл, не требует установки Python.

### Сборка через PowerShell

```powershell
.\build_release.ps1
```

### Продакшн-запуск веб-сервера

```powershell
# Убедитесь что venv активирован
.venv\Scripts\activate

# Продакшн (без --reload, с несколькими воркерами)
python -m uvicorn web.main:app --host 0.0.0.0 --port 8000 --workers 4
```

> `--workers 4` несовместим с `--reload`. Используйте `--workers` только в продакшне.

---

## Git-процесс

Подробные правила описаны в `.agents/skills/git-workflow/SKILL.md`.

### Ветки

| Ветка | Назначение |
|---|---|
| `main` | Продакшн. Прямой push запрещён |
| `debug` | Сборка всех изменений, тестирование |
| `feature/*` | Новая функциональность |
| `bugfix/*` | Исправление багов |
| `hotfix/*` | Срочные исправления |
| `refactor/*` | Рефакторинг |

### Процесс

```
1. git checkout debug && git pull
2. git checkout -b feature/название-фичи
3. ... работа ...
4. git commit -m "компонент: что было → что стало"
5. git push -u origin feature/название-фичи
6. git checkout debug && git merge feature/название-фичи
7. git push origin debug
```

Мерж в `main` — только после проверки `debug`.

---

## Зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| PyQt6 | ≥ 6.6 | Десктоп GUI |
| SQLAlchemy | ≥ 2.0 | ORM |
| FastAPI | ≥ 0.115, < 0.136 | Веб-фреймворк |
| Starlette | ≥ 0.40, < 0.42 | ASGI-фреймворк |
| Jinja2 | 3.1.4 | Шаблонизатор |
| uvicorn | ≥ 0.30 | ASGI-сервер |
| psycopg2-binary | ≥ 2.9 | PostgreSQL-адаптер |
| openpyxl | ≥ 3.1 | Excel-генерация |
| matplotlib | ≥ 3.8 | Графики (десктоп) |
| fastapi-csrf-protect | ≥ 1.0.7 | CSRF-защита |
| websockets | ≥ 13.0 | WebSocket |
| python-dotenv | ≥ 1.0 | Чтение .env |
| pyinstaller | ≥ 6.0 | Сборка .exe |

> **Важно:** Jinja2 зафиксирован на 3.1.4. Версии 3.1.5+ ломают кэш шаблонов при работе со Starlette.

---

## Лицензия

Проприетарный проект. Все права защищены.
