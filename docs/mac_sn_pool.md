# MAC-пул и SN-пул

## MAC-пул (MAC Address Pool)

### Назначение
Управление пулом MAC-адресов для устройств. При создании проекта устройствам автоматически назначаются MAC из пула.

### Структура (pm_mac_addresses)

| Поле | Описание |
|------|----------|
| `mac` | MAC-адрес в формате `XX:XX:XX:XX:XX:XX` |
| `is_used` | Занят ли адрес |
| `device_id` | FK на устройство (если занят) |
| `category` | Категория: ETH, WIFI |

### API

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/mac-pool/stats` | Статистика пула |
| POST | `/api/mac-pool/import` | Импорт MAC из файла |
| POST | `/api/mac-pool/generate` | Генерация диапазона |

### Автоматическое назначение

При создании устройства (`_next_free_mac()`):
1. Ищет первый свободный MAC из пула (`is_used=False`)
2. Если пул пуст → генерирует новый = последний MAC + 1
3. Помечает как занятый (`is_used=True, device_id=X`)

При удалении проекта MAC-адреса освобождаются (`is_used=False, device_id=None`).

### Категории устройств

- **DUAL_MAC_CATEGORIES** — устройства с двумя MAC (ETH + Wi-Fi)
- **SINGLE_MAC_CATEGORIES** — один MAC (только ETH)

---

## SN-пул (Serial Number Pool)

### Назначение
Пул серийных номеров для автоматического назначения устройствам при создании проекта.

### API

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/sn-pool` | Список SN в пуле |
| POST | `/api/sn-pool/import` | Импорт SN из файла |
| POST | `/api/sn-pool/generate` | Генерация диапазона |
| DELETE | `/api/sn-pool/{id}` | Удалить SN |

### WS Broadcast

При изменении пула отправляется `sn_pool_updated`.

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/mac_pool_api.py` | CRUD MAC-пула |
| `web/api/sn_pool_api.py` | CRUD SN-пула |
| `web/api/projects_api.py` | `_next_free_mac()` — автоназначение |
| `src/models.py` | ORM: MacAddress, SerialNumber |
