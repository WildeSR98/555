# Отправка фото (Photo Transfer)

## Назначение
Перемещение фотографий устройств с локального ПК рабочего поста на сетевую шару (`\\192.168.106.29\PR_DEP`).

## Flow

```
1. Работник фотографирует устройство → фото попадают в C:\Photos\Upload
2. На посту сканирования нажимает кнопку «📷 Отправить фото»
3. Бэкенд:
   a. Находит все изображения в IMG_SOURCE_DIR
   b. Подключается к сетевой шаре (WNetAddConnection2W)
   c. Формирует путь: \\server\share\Assembly\{project_name}\{post_folder}\{SN}\
   d. Перемещает файлы (shutil.move)
   e. Открывает Explorer с папкой назначения
```

## Маппинг поста → подпапки

| Workplace type | Папка на шаре |
|----------------|---------------|
| PRE_PRODUCTION | Complectation |
| VIBROSTAND | Vibrostand |
| TECH_CONTROL_1_1/1_2/2_1/2_2 | OTK |
| FUNC_CONTROL | Tests |
| PACKING | Packing |
| WAREHOUSE | Warehouse |

## Настройки (.env)

| Переменная | Описание | Default |
|------------|----------|---------|
| `IMG_SOURCE_DIR` | Локальная папка с фото | `C:\Photos\Upload` |
| `IMG_NET_SERVER` | Сервер шары | `\\192.168.106.29` |
| `IMG_NET_SHARE` | Имя шары | `PR_DEP` |
| `IMG_NET_USER` | Логин | `PR_DEP` |
| `IMG_NET_PASS` | Пароль | `P@ssw0rd` |
| `IMG_NET_BASE` | Базовая папка | `Assembly` |
| `IMG_EXTENSIONS` | Расширения файлов | `jpg,jpeg,png,bmp,gif,webp,tiff,tif` |

## API

```
POST /api/scan/send-photos
  Body: { sn, device_id, workplace_id }
  Response: { ok, copied, dest, files, errors }
```

## UI

- Кнопка «📷 Отправить фото» — доступна когда устройство в буфере
- Статус: синий (загрузка) → зелёный (успех) → жёлтый (нет фото) → красный (ошибка)

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `web/api/scan_api.py` | Endpoint `send-photos`, подключение к шаре |
| `web/templates/scan.html` | UI кнопки и статуса `sendDevicePhotos()` |
