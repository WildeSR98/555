# Production Manager — Web Interface

Веб-интерфейс системы управления производством на базе **FastAPI + Jinja2 + Chart.js**.

## Структура

```
web/
├── main.py                 # Точка входа FastAPI
├── __init__.py
├── api/                    # REST API эндпоинты (JSON)
│   ├── dashboard_api.py    # Статистика и графики дашборда
│   ├── analytics_api.py    # Аналитика по устройствам и пользователям
│   ├── projects_api.py     # Данные проектов
│   ├── pipeline_api.py     # Конвейер производства
│   ├── devices_api.py      # Устройства с фильтрацией
│   ├── sn_pool_api.py      # Пул серийных номеров
│   └── admin_api.py        # Админ-панель
├── routes/                 # HTML страницы
│   ├── auth.py             # Авторизация (вход/выход)
│   ├── dashboard.py        # Дашборд
│   ├── analytics.py        # Аналитика
│   ├── projects.py         # Проекты
│   ├── pipeline.py         # Конвейер
│   ├── scan.py             # Сканирование
│   ├── devices.py          # Устройства
│   ├── sn_pool.py          # SN Пул
│   └── admin.py            # Админ-панель
├── templates/              # Jinja2 HTML шаблоны
│   ├── base.html           # Базовый layout с навигацией
│   ├── login.html          # Страница входа
│   ├── dashboard.html      # Дашборд с графиками Chart.js
│   ├── analytics.html      # Аналитика с графиками
│   ├── projects.html       # Список проектов
│   ├── pipeline.html       # Конвейер (карточки устройств)
│   ├── scan.html           # Сканирование SN
│   ├── devices.html        # Таблица устройств
│   ├── sn_pool.html        # Таблица SN
│   └── admin.html          # Управление пользователями
└── static/                 # Статические файлы
    ├── css/
    │   └── main.css        # Основные стили
    └── js/
        └── main.js         # Утилиты JS (fetch, уведомления, автообновление)
```

## Запуск

### 1. Убедитесь, что PostgreSQL работает

```bash
docker-compose up -d
```

### 2. Настройте .env

```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=production_db
DB_USER=prod_user
DB_PASSWORD=strong_password_here
```

### 3. Запустите веб-сервер

```bash
# Разработка (автообновление)
python -m uvicorn web.main:app --reload --port 8000

# Продакшн
python -m uvicorn web.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Откройте браузер

- **Веб-приложение**: http://localhost:8000
- **API документация (Swagger)**: http://localhost:8000/docs
- **API схема (ReDoc)**: http://localhost:8000/redoc

## Доступные страницы

| Страница       | URL               | Описание                          |
|----------------|-------------------|-----------------------------------|
| Вход           | `/login`          | Авторизация                       |
| Дашборд        | `/dashboard`      | Общая статистика, графики         |
| Аналитика      | `/analytics`      | Детальная аналитика, топы         |
| Проекты        | `/projects`       | Список проектов                   |
| Конвейер       | `/pipeline`       | Устройства в производстве         |
| Скан           | `/scan`           | Сканирование SN                   |
| Устройства     | `/devices`        | Все устройства                    |
| SN Пул         | `/sn-pool`        | Управление серийными номерами     |
| Админ          | `/admin`          | Управление пользователями         |

## API эндпоинты

Все API доступны в `/api/<module>/`:

- `GET /api/dashboard/` — статистика дашборда
- `GET /api/dashboard/chart-data` — данные для графиков
- `GET /api/analytics/` — общая аналитика
- `GET /api/analytics/devices` — аналитика по устройствам
- `GET /api/analytics/users` — аналитика по пользователям
- `GET /api/projects/` — список проектов
- `GET /api/projects/{id}` — конкретный проект
- `GET /api/pipeline/` — устройства в производстве
- `GET /api/devices/` — устройства (с фильтрацией `?search=&status=`)
- `GET /api/devices/statuses` — статусы с количеством
- `GET /api/sn-pool/` — серийные номера
- `GET /api/admin/users` — пользователи
- `GET /api/admin/stats` — статистика админки

## Технологии

- **FastAPI** — асинхронный веб-фреймворк
- **Uvicorn** — ASGI сервер
- **Jinja2** — шаблонизатор
- **Chart.js** — графики и диаграммы
- **SQLAlchemy** — ORM (переиспользуется из desktop-версии)
- **PostgreSQL** — база данных (из Docker)

## Особенности

✅ Переиспользует модели `src/models.py` и подключение `src/database.py`  
✅ Авторизация через ту же таблицу `accounts_user`  
✅ Сессии хранятся в cookie (secure, httpOnly)  
✅ Автообновление страниц каждые 30 секунд  
✅ Адаптивный дизайн (mobile-friendly)  
✅ Современный UI с тёмной боковой панелью  
