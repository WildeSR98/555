"""
Скрипт синхронизации изображений с локальной папки на сетевой диск.
Можно запускать:
  1. Напрямую: python scripts/sync_images_to_network.py
  2. Через FastAPI эндпоинт (web/api/admin_api.py)

Настройки — через переменные окружения или .env:
  IMG_SOURCE_DIR   — откуда берём изображения (локальная папка)
  IMG_TARGET_DIR   — куда копируем (сетевой диск / UNC путь)
  IMG_EXTENSIONS   — расширения через запятую (по умолчанию: jpg,jpeg,png,bmp,gif,webp)
  IMG_DELETE_AFTER — удалять оригинал после копирования (True/False, по умолчанию False)
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Загружаем .env из корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=True)

# ─── Настройки ────────────────────────────────────────────────────────────────

SOURCE_DIR   = Path(os.getenv('IMG_SOURCE_DIR', r'C:\Users\Public\Pictures\Upload'))
TARGET_DIR   = Path(os.getenv('IMG_TARGET_DIR', r'\\server\share\photos'))
EXTENSIONS   = {f".{e.strip().lower()}" for e in os.getenv('IMG_EXTENSIONS', 'jpg,jpeg,png,bmp,gif,webp').split(',')}
DELETE_AFTER = os.getenv('IMG_DELETE_AFTER', 'False').lower() in ('true', '1', 'yes')

# ─── Лог ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ─── Логика ───────────────────────────────────────────────────────────────────

def sync_images(
    source: Path = SOURCE_DIR,
    target: Path = TARGET_DIR,
    extensions: set = EXTENSIONS,
    delete_after: bool = DELETE_AFTER,
    subdir: str = '',       # подпапка в target (напр. по дате или проекту)
) -> dict:
    """
    Копирует изображения из source в target.
    Возвращает словарь с результатами: {copied, skipped, errors, files}.
    """
    result = {'copied': 0, 'skipped': 0, 'errors': 0, 'files': [], 'error_files': []}

    if not source.exists():
        msg = f"Папка источника не найдена: {source}"
        log.error(msg)
        return {**result, 'error': msg}

    # Конечная папка с подпапкой (если передана)
    dest = target / subdir if subdir else target

    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        msg = f"Не удалось создать папку назначения {dest}: {e}"
        log.error(msg)
        return {**result, 'error': msg}

    # Перебираем файлы в источнике (не рекурсивно)
    image_files = [f for f in source.iterdir() if f.is_file() and f.suffix.lower() in extensions]

    if not image_files:
        log.info(f"Нет изображений для копирования в {source}")
        return result

    log.info(f"Найдено изображений: {len(image_files)} в {source}")

    for img in image_files:
        dest_file = dest / img.name

        # Если файл уже существует — пропускаем (или можно добавить суффикс)
        if dest_file.exists():
            log.info(f"  [SKIP] {img.name} — уже существует")
            result['skipped'] += 1
            continue

        try:
            shutil.copy2(img, dest_file)   # copy2 сохраняет метаданные
            log.info(f"  [OK]   {img.name} → {dest_file}")
            result['copied'] += 1
            result['files'].append(img.name)

            if delete_after:
                img.unlink()
                log.info(f"  [DEL]  {img.name} удалён из источника")

        except Exception as e:
            log.error(f"  [ERR]  {img.name}: {e}")
            result['errors'] += 1
            result['error_files'].append({'file': img.name, 'error': str(e)})

    log.info(f"Готово: скопировано={result['copied']}, пропущено={result['skipped']}, ошибок={result['errors']}")
    return result


# ─── Запуск напрямую ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Синхронизация изображений на сетевой диск')
    parser.add_argument('--source', type=Path, default=SOURCE_DIR, help='Папка источника')
    parser.add_argument('--target', type=Path, default=TARGET_DIR, help='Папка назначения')
    parser.add_argument('--subdir', type=str, default='',           help='Подпапка в target')
    parser.add_argument('--delete', action='store_true',            help='Удалять оригиналы после копирования')
    args = parser.parse_args()

    result = sync_images(
        source=args.source,
        target=args.target,
        subdir=args.subdir,
        delete_after=args.delete,
    )

    sys.exit(0 if result.get('errors', 0) == 0 else 1)
