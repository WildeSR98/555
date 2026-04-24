"""
API для управления пулом MAC-адресов.
"""
import re
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.models import MacAddress, Device, User
from web.dependencies import get_current_user

router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────

_MAC_STRIP = re.compile(r'[^0-9a-fA-F]')

def normalize_mac(raw: str) -> Optional[str]:
    """Нормализует MAC в формат XX:XX:XX:XX:XX:XX. Возвращает None при ошибке."""
    digits = _MAC_STRIP.sub('', raw.strip())
    if len(digits) != 12:
        return None
    return ':'.join(digits[i:i+2].upper() for i in range(0, 12, 2))


# ── Schemas ────────────────────────────────────────────────────────────────────

class MacManualInput(BaseModel):
    mac:      str
    mac_type: str   # 'LAN' | 'IDRAC'


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get('/stats')
def get_mac_stats(db: Session = Depends(get_db)):
    """Статистика пула MAC-адресов.
    MAC выдаются попарно (LAN + BMC), поэтому показываем только LAN-счётчик.
    """
    total_lan = db.query(MacAddress).filter_by(mac_type='LAN').count()
    free_lan  = db.query(MacAddress).filter_by(mac_type='LAN', is_used=False).count()
    # BMC тоже считаем для полноты картины, но не отображаем отдельно
    total_bmc = db.query(MacAddress).filter_by(mac_type='IDRAC').count()
    free_bmc  = db.query(MacAddress).filter_by(mac_type='IDRAC', is_used=False).count()
    return {
        'lan':   {'total': total_lan, 'free': free_lan,  'used': total_lan - free_lan},
        'idrac': {'total': total_bmc, 'free': free_bmc,  'used': total_bmc - free_bmc},
    }


@router.get('/paired')
def list_macs_paired(
    used:   str = 'ALL',   # FREE | USED | ALL
    search: str = '',
    limit:  int = 300,
    db: Session = Depends(get_db),
):
    """
    Список MAC-адресов сгруппированных по устройству: одна строка = SN + проект + LAN + BMC.
    Свободные MAC (без устройства) device_id=None — отображаем как отдельные строки.
    """
    from src.models import Project
    from sqlalchemy.orm import joinedload

    q = db.query(MacAddress).options(joinedload(MacAddress.device))

    if used.upper() == 'FREE':
        q = q.filter(MacAddress.is_used == False)
    elif used.upper() == 'USED':
        q = q.filter(MacAddress.is_used == True)
    if search:
        q = q.filter(MacAddress.mac.contains(search.upper()))

    all_rows = q.order_by(MacAddress.device_id.desc(), MacAddress.mac_type).limit(limit * 2).all()

    # Группируем по device_id
    from collections import defaultdict
    by_device: dict = defaultdict(lambda: {'lan': None, 'bmc': None, 'device': None})
    free_lans = []   # свободные LAN (device_id is None)
    free_bmcs = []   # свободные BMC

    for r in all_rows:
        if r.device_id is None:
            if r.mac_type == 'LAN':
                free_lans.append(r)
            else:
                free_bmcs.append(r)
        else:
            key = r.device_id
            by_device[key]['device'] = r.device
            if r.mac_type == 'LAN':
                by_device[key]['lan'] = r
            else:
                by_device[key]['bmc'] = r

    result = []

    # Сначала используемые пары
    for dev_id, info in by_device.items():
        dev = info['device']
        lan = info['lan']
        bmc = info['bmc']
        project_name = ''
        if dev and dev.project_id:
            proj = db.query(Project).get(dev.project_id)
            project_name = proj.name if proj else ''
        result.append({
            'device_sn':    dev.serial_number if dev else None,
            'project_name': project_name,
            'lan_mac':      lan.mac if lan else None,
            'bmc_mac':      bmc.mac if bmc else None,
            'lan_id':       lan.id  if lan else None,
            'bmc_id':       bmc.id  if bmc else None,
            'is_used':      True,
            'created_at':   (lan or bmc).created_at.strftime('%d.%m.%Y') if (lan or bmc) else None,
        })

    # Свободные LAN — паруем с BMC по индексу
    for i, lan in enumerate(free_lans):
        bmc = free_bmcs[i] if i < len(free_bmcs) else None
        result.append({
            'device_sn':    None,
            'project_name': None,
            'lan_mac':      lan.mac,
            'bmc_mac':      bmc.mac if bmc else None,
            'lan_id':       lan.id,
            'bmc_id':       bmc.id if bmc else None,
            'is_used':      False,
            'created_at':   lan.created_at.strftime('%d.%m.%Y') if lan.created_at else None,
        })
    # BMC без пары
    for bmc in free_bmcs[len(free_lans):]:
        result.append({
            'device_sn':    None,
            'project_name': None,
            'lan_mac':      None,
            'bmc_mac':      bmc.mac,
            'lan_id':       None,
            'bmc_id':       bmc.id,
            'is_used':      False,
            'created_at':   bmc.created_at.strftime('%d.%m.%Y') if bmc.created_at else None,
        })

    return result[:limit]


@router.get('/list')
def list_macs(
    mac_type: str = 'ALL',   # LAN | IDRAC | ALL
    used:     str = 'ALL',   # FREE | USED | ALL
    search:   str = '',
    limit:    int = 200,
    db: Session = Depends(get_db),
):
    """Список MAC-адресов с фильтрами."""
    q = db.query(MacAddress)
    if mac_type.upper() in ('LAN', 'IDRAC'):
        q = q.filter(MacAddress.mac_type == mac_type.upper())
    if used.upper() == 'FREE':
        q = q.filter(MacAddress.is_used == False)
    elif used.upper() == 'USED':
        q = q.filter(MacAddress.is_used == True)
    if search:
        q = q.filter(MacAddress.mac.contains(search.upper()))

    rows = q.order_by(MacAddress.id.desc()).limit(limit).all()
    return [
        {
            'id':         r.id,
            'mac':        r.mac,
            'mac_type':   r.mac_type,
            'is_used':    r.is_used,
            'device_id':  r.device_id,
            'device_sn':  r.device.serial_number if r.device else None,
            'created_at': r.created_at.strftime('%d.%m.%Y') if r.created_at else None,
        }
        for r in rows
    ]


@router.post('/add')
def add_mac_manual(
    data: MacManualInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Добавить один MAC вручную."""
    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, 'Недостаточно прав')
    mac = normalize_mac(data.mac)
    if not mac:
        raise HTTPException(400, f'Неверный формат MAC: {data.mac!r}')
    if data.mac_type.upper() not in ('LAN', 'IDRAC'):
        raise HTTPException(400, 'mac_type должен быть LAN или IDRAC (BMC)')
    if db.query(MacAddress).filter_by(mac=mac).first():
        raise HTTPException(400, f'MAC {mac} уже существует в пуле')
    db.add(MacAddress(mac=mac, mac_type=data.mac_type.upper(), is_used=False, created_at=datetime.now()))
    db.commit()
    return {'ok': True, 'mac': mac}


@router.post('/import')
async def import_macs_from_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Импорт MAC-адресов из Excel (.xlsx) или CSV.

    Excel-формат (2 колонки, без заголовка или с заголовком):
        | MAC               | Тип   |
        |-------------------|-------|
        | AA:BB:CC:DD:EE:01 | LAN   |
        | AA:BB:CC:DD:EE:02 | BMC   |

    CSV-формат: mac,type  (через запятую или точку с запятой)
    """
    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, 'Недостаточно прав')

    content = await file.read()
    filename = (file.filename or '').lower()
    rows: list[tuple[str, str]] = []   # [(mac_raw, type_raw)]

    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=1, values_only=True):
                if not row or row[0] is None:
                    continue
                mac_raw  = str(row[0]).strip()
                type_raw = str(row[1]).strip().upper() if len(row) > 1 and row[1] else 'LAN'
                rows.append((mac_raw, type_raw))
        except Exception as e:
            raise HTTPException(400, f'Ошибка чтения Excel: {e}')
    else:
        # CSV / TXT
        text_data = content.decode('utf-8', errors='replace')
        for line in text_data.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = re.split(r'[,;|\t]', line, maxsplit=1)
            mac_raw  = parts[0].strip()
            type_raw = parts[1].strip().upper() if len(parts) > 1 else 'LAN'
            rows.append((mac_raw, type_raw))

    added = skipped_dup = skipped_bad = 0
    for mac_raw, type_raw in rows:
        mac = normalize_mac(mac_raw)
        if not mac:
            skipped_bad += 1
            continue
        if type_raw not in ('LAN', 'IDRAC'):
            type_raw = 'LAN'
        # Пропустить заголовочную строку
        if mac_raw.upper() in ('MAC', 'MAC ADDRESS', 'ADDRESS'):
            continue
        if db.query(MacAddress).filter_by(mac=mac).first():
            skipped_dup += 1
            continue
        db.add(MacAddress(mac=mac, mac_type=type_raw, is_used=False, created_at=datetime.now()))
        added += 1

    if added:
        db.commit()

    return {
        'ok':          True,
        'added':       added,
        'skipped_dup': skipped_dup,
        'skipped_bad': skipped_bad,
        'message':     f'Добавлено: {added}, дублей: {skipped_dup}, ошибок формата: {skipped_bad}',
    }


@router.delete('/{mac_id}')
def delete_mac(
    mac_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Удалить свободный MAC из пула."""
    if user.role not in ('ADMIN', 'ROOT'):
        raise HTTPException(403, 'Недостаточно прав')
    rec = db.query(MacAddress).get(mac_id)
    if not rec:
        raise HTTPException(404, 'MAC не найден')
    if rec.is_used:
        raise HTTPException(400, f'MAC {rec.mac} уже используется устройством — нельзя удалить')
    db.delete(rec)
    db.commit()
    return {'ok': True, 'message': f'MAC {rec.mac} удалён'}
