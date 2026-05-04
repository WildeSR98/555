# Администрирование (Admin Panel)

## Назначение
Управление пользователями, рабочими местами, системными настройками, архивом.

## Роли пользователей

| Роль | Код | Права |
|------|-----|-------|
| ROOT | `ROOT` | Полный доступ, действия не логируются |
| Администратор | `ADMIN` | Управление пользователями, удаление проектов |
| Менеджер | `MANAGER` | Создание проектов, маршрутов |
| Начальник цеха | `SHOP_MANAGER` | Управление постами |
| Работник | `WORKER` | Только сканирование |

## API Endpoints (admin_api.py)

### Пользователи

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/admin/users` | Список пользователей |
| POST | `/api/admin/users` | Создать пользователя |
| PUT | `/api/admin/users/{id}` | Обновить |
| POST | `/api/admin/users/{id}/toggle-active` | Деактивировать/активировать |

### Рабочие места

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/admin/workplaces` | Список рабочих мест |
| POST | `/api/admin/workplaces` | Создать |
| PUT | `/api/admin/workplaces/{id}` | Обновить |
| DELETE | `/api/admin/workplaces/{id}` | Удалить |
| POST | `/api/admin/workplaces/reorder` | Изменить порядок |

### Системные настройки

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/admin/system-config` | Все настройки |
| PUT | `/api/admin/system-config/{key}` | Обновить настройку |
| POST | `/api/admin/broadcast` | Широковещательное сообщение |

### Настраиваемые параметры (pm_system_config)

| Ключ | Описание | Default |
|------|----------|---------|
| `route_bypass_roles` | Роли, обходящие проверку маршрута | `ADMIN,ROOT` |
| `cooldown_bypass_roles` | Роли, обходящие cooldown | `ADMIN,MANAGER,SHOP_MANAGER,ROOT` |

## Авторизация

- Login/Logout через cookie-сессию (Starlette SessionMiddleware)
- `POST /login` → проверка username/password → session['user_id']
- `GET /logout` → session.clear()

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/admin_api.py` | Все admin endpoints |
| `web/templates/admin.html` | UI панели администратора |
| `src/system_config.py` | Чтение настроек из pm_system_config |
| `web/dependencies.py` | `get_current_user()` — dependency для авторизации |
