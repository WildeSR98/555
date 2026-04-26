from datetime import datetime, timedelta
from typing import Optional, Tuple
from ..models import User, Device, WorkLog

class WorkflowEngine:
    """Логика переходов состояний (логика Влада) и ограничения."""

    # Разрешенные переходы (откуда -> [куда])
    # Если старого статуса нет в списке, переход свободный (например, для начальных этапов)
    # Разрешенные переходы (статус -> [возможные следующие статусы])
    # Некоторые workplace_type используют нестандартные входные статусы устройств
    WORKPLACE_ENTRY_STATUS = {
        'PRE_PRODUCTION': 'WAITING_KITTING',   # пост Комплектовки принимает WAITING_KITTING
        'KITTING':        'WAITING_KITTING',
    }

    STRICT_TRANSITIONS = {
        'WAITING_KITTING': ['PRE_PRODUCTION', 'KITTING', 'REPAIR', 'DEFECT'],
        'KITTING': ['WAITING_ASSEMBLY', 'REPAIR', 'DEFECT'],
        'WAITING_ASSEMBLY': ['ASSEMBLY', 'REPAIR', 'DEFECT'],
        'ASSEMBLY': ['WAITING_VIBROSTAND', 'REPAIR', 'DEFECT'],
        'WAITING_VIBROSTAND': ['VIBROSTAND', 'REPAIR', 'DEFECT'],
        'VIBROSTAND': ['WAITING_TECH_CONTROL_1_1', 'WAITING_TECH_CONTROL_1_2', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_1_1': ['WAITING_TECH_CONTROL_1_2', 'REPAIR', 'DEFECT'],
        'PRE_PRODUCTION': ['WAITING_ASSEMBLY', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_1_2': ['WAITING_FUNC_CONTROL', 'REPAIR', 'DEFECT'],
        'FUNC_CONTROL': ['WAITING_TECH_CONTROL_2_1', 'WAITING_TECH_CONTROL_2_2', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_2_1': ['WAITING_TECH_CONTROL_2_2', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_2_2': ['WAITING_PACKING', 'REPAIR', 'DEFECT'],
        'WAITING_PACKING': ['PACKING', 'REPAIR', 'DEFECT'],
        'PACKING': ['WAITING_ACCOUNTING', 'REPAIR', 'DEFECT'],
        'WAITING_ACCOUNTING': ['ACCOUNTING', 'REPAIR', 'DEFECT'],
        'ACCOUNTING': ['WAITING_WAREHOUSE', 'REPAIR', 'DEFECT'],
        'WAITING_WAREHOUSE': ['WAREHOUSE', 'REPAIR', 'DEFECT'],
        'WAREHOUSE': ['QC_PASSED', 'REPAIR', 'DEFECT'],
        'REPAIR': [
            'WAITING_KITTING',
            'WAITING_ASSEMBLY', 'WAITING_VIBROSTAND',
            'WAITING_TECH_CONTROL_1_1', 'WAITING_TECH_CONTROL_1_2',
            'WAITING_FUNC_CONTROL',
        ]
    }

    COOLDOWN_MINUTES = 5

    @staticmethod
    def can_change_status(
        device: Device, 
        new_status: str, 
        user: User, 
        last_log: Optional[WorkLog] = None,
        cooldown_bypass_roles: Optional[list] = None,
        cooldown_seconds: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Проверка: можно ли перевести устройство в новый статус.
        Возвращает (Успех, Сообщение об ошибке)
        """
        # 1. Привилегированные роли (обходят кулдаун и жёсткие ограничения)
        _bypass = cooldown_bypass_roles if cooldown_bypass_roles is not None else [
            User.ROLE_ADMIN, User.ROLE_MANAGER, User.ROLE_SHOP_MANAGER, User.ROLE_ROOT
        ]
        if user.role in _bypass:
            return True, ""

        # 2. Проверка кулдауна (из таймера маршрута или дефолт 5 минут)
        cd = cooldown_seconds if cooldown_seconds is not None else (WorkflowEngine.COOLDOWN_MINUTES * 60)
        if last_log and cd > 0:
            time_passed = datetime.now() - last_log.created_at
            if time_passed < timedelta(seconds=cd):
                remaining = int(cd - time_passed.total_seconds())
                m = remaining // 60
                s = remaining % 60
                return False, f"Ожидайте таймер. Осталось {m}:{s:02d}."

        # 3. Проверка логики переходов (Vlad's Logic)
        old_status = device.status
        
        # Ремонт доступен всегда
        if new_status == 'REPAIR' or new_status == 'DEFECT':
            return True, ""

        if old_status in WorkflowEngine.STRICT_TRANSITIONS:
            allowed = WorkflowEngine.STRICT_TRANSITIONS[old_status]
            if new_status not in allowed:
                return False, f"Нарушение маршрута: после {device.status_display} нельзя {Device.STATUS_DISPLAY.get(new_status, new_status)}."

        return True, ""

    @staticmethod
    def can_accept_device(workplace_type: str, device_status: str) -> Tuple[bool, str]:
        """
        Проверка: может ли данный пост принять устройство с текущим статусом.
        Пример: Пост ASSEMBLY может принять только WAITING_ASSEMBLY.
        """
        if workplace_type == 'REPAIR':
            return True, "" # Ремонт принимает всё

        # Для постов с нестандартным входным статусом используем явный маппинг
        if workplace_type in WorkflowEngine.WORKPLACE_ENTRY_STATUS:
            expected_status = WorkflowEngine.WORKPLACE_ENTRY_STATUS[workplace_type]
        else:
            # Правило по умолчанию: Пост Х принимает устройство, если статус = WAITING_X
            expected_status = f"WAITING_{workplace_type}"

        if device_status != expected_status and device_status != workplace_type:
            from ..models import Device
            
            PREV_POST_MAP = {
                'WAITING_KITTING': 'Задание создано',
                'WAITING_PRE_PRODUCTION': 'Начальный этап',
                'WAITING_ASSEMBLY': 'Комплектовка',
                'WAITING_VIBROSTAND': 'Сборка',
                'WAITING_TECH_CONTROL_1_1': 'Вибростенд',
                'WAITING_TECH_CONTROL_1_2': 'Тех. контроль 1.1',
                'WAITING_FUNC_CONTROL': 'Тех. контроль 1.2',
                'WAITING_TECH_CONTROL_2_1': 'Функц. контроль',
                'WAITING_TECH_CONTROL_2_2': 'Тех. контроль 2.1',
                'WAITING_PACKING': 'Тех. контроль 2.2',
                'WAITING_ACCOUNTING': 'Упаковка',
                'WAITING_WAREHOUSE': 'Учёт',
            }
            
            prev_post_name = PREV_POST_MAP.get(expected_status, "Предыдущий этап")
            status_display = Device.STATUS_DISPLAY.get(device_status, device_status)
            
            if device_status in ['DEFECT', 'WAITING_PARTS', 'WAITING_SOFTWARE', 'SHIPPED']:
                return False, f"Устройство находится в статусе «{status_display}»."

            try:
                curr_idx = Device.PIPELINE_STAGES.index(device_status)
                exp_idx = Device.PIPELINE_STAGES.index(expected_status)
                if curr_idx > exp_idx:
                    return False, f"Устройство уже прошло этот этап. Текущий статус: «{status_display}»."
                else:
                    return False, f"Устройство не прошло пост «{prev_post_name}». Текущий статус: «{status_display}»."
            except ValueError:
                return False, f"Ожидается прохождение этапа «{prev_post_name}» (Текущий статус: {status_display})."

        return True, ""

    @staticmethod
    def is_batch_allowed(workplace_type: str) -> bool:
        """Проверка: разрешен ли пакетный ввод для данного типа поста."""
        # Вибро, Тесты, Упаковка, Склад
        allowed_types = [
            'VIBROSTAND', 'FUNC_CONTROL', 'TECH_CONTROL_1_1', 
            'TECH_CONTROL_1_2', 'TECH_CONTROL_2_1', 'TECH_CONTROL_2_2',
            'PACKING', 'ACCOUNTING', 'WAREHOUSE'
        ]
        return workplace_type in allowed_types

    @staticmethod
    def get_batch_limit(workplace_type: str) -> int:
        """Лимит пакетного ввода."""
        if workplace_type == 'WAREHOUSE':
            return 100
        if WorkflowEngine.is_batch_allowed(workplace_type):
            return 10
        return 1
