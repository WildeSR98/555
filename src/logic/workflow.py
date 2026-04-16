from datetime import datetime, timedelta
from typing import Optional, Tuple
from ..models import User, Device, WorkLog

class WorkflowEngine:
    """Логика переходов состояний (логика Влада) и ограничения."""

    # Разрешенные переходы (откуда -> [куда])
    # Если старого статуса нет в списке, переход свободный (например, для начальных этапов)
    # Разрешенные переходы (статус -> [возможные следующие статусы])
    STRICT_TRANSITIONS = {
        'WAITING_KITTING': ['WAITING_PRE_PRODUCTION', 'REPAIR', 'DEFECT'],
        'KITTING': ['WAITING_PRE_PRODUCTION', 'REPAIR', 'DEFECT'],
        'WAITING_PRE_PRODUCTION': ['PRE_PRODUCTION', 'REPAIR', 'DEFECT'],
        'PRE_PRODUCTION': ['WAITING_ASSEMBLY', 'REPAIR', 'DEFECT'],
        'WAITING_ASSEMBLY': ['ASSEMBLY', 'REPAIR', 'DEFECT'],
        'ASSEMBLY': ['WAITING_VIBROSTAND', 'REPAIR', 'DEFECT'],
        'WAITING_VIBROSTAND': ['VIBROSTAND', 'REPAIR', 'DEFECT'],
        'VIBROSTAND': ['WAITING_TECH_CONTROL_1_1', 'WAITING_TECH_CONTROL_1_2', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_1_1': ['WAITING_FUNC_CONTROL', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_1_2': ['WAITING_FUNC_CONTROL', 'REPAIR', 'DEFECT'],
        'FUNC_CONTROL': ['WAITING_TECH_CONTROL_2_1', 'WAITING_TECH_CONTROL_2_2', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_2_1': ['WAITING_PACKING', 'REPAIR', 'DEFECT'],
        'TECH_CONTROL_2_2': ['WAITING_PACKING', 'REPAIR', 'DEFECT'],
        'WAITING_PACKING': ['PACKING', 'REPAIR', 'DEFECT'],
        'PACKING': ['WAITING_ACCOUNTING', 'REPAIR', 'DEFECT'],
        'WAITING_ACCOUNTING': ['ACCOUNTING', 'REPAIR', 'DEFECT'],
        'ACCOUNTING': ['WAREHOUSE', 'QC_PASSED', 'REPAIR', 'DEFECT'],
        'REPAIR': [
            'WAITING_VIBROSTAND', 'WAITING_TECH_CONTROL_1_1', 'WAITING_TECH_CONTROL_1_2', 
            'WAITING_PACKING', 'WAITING_ASSEMBLY', 'WAITING_PRE_PRODUCTION'
        ]
    }

    COOLDOWN_MINUTES = 5

    @staticmethod
    def can_change_status(
        device: Device, 
        new_status: str, 
        user: User, 
        last_log: Optional[WorkLog] = None
    ) -> Tuple[bool, str]:
        """
        Проверка: можно ли перевести устройство в новый статус.
        Возвращает (Успех, Сообщение об ошибке)
        """
        # 1. Права Начцеха / Админа / Менеджера (Manager/Admin/ShopManager могут всё)
        if user.role in [User.ROLE_ADMIN, User.ROLE_MANAGER, User.ROLE_SHOP_MANAGER]:
            return True, ""

        # 2. Проверка кулдауна (5 минут)
        if last_log:
            time_passed = datetime.now() - last_log.created_at
            if time_passed < timedelta(minutes=WorkflowEngine.COOLDOWN_MINUTES):
                remaining = int(WorkflowEngine.COOLDOWN_MINUTES * 60 - time_passed.total_seconds())
                return False, f"Смена статуса запрещена. Прошло меньше 5 минут (осталось {remaining} сек)."

        # 3. Проверка логики переходов (Vlad's Logic)
        old_status = device.status
        
        # Ремонт доступен всегда
        if new_status == 'REPAIR' or new_status == 'DEFECT':
            return True, ""

        if old_status in WorkflowEngine.STRICT_TRANSITIONS:
            allowed = WorkflowEngine.STRICT_TRANSITIONS[old_status]
            if new_status not in allowed:
                return False, f"Нарушение маршрута: после {device.status_display} нельзя {Device.STATUS_DISPLAY.get(new_status, new_status)}."

        # После Сборки — только Вибро (или Ремонт/Брак)
        if old_status == 'ASSEMBLY' and new_status not in ['WAITING_VIBROSTAND', 'VIBROSTAND', 'REPAIR', 'DEFECT']:
             return False, "После сборки устройство должно идти только на Вибростенд."

        # После Вибро — только ОТК (или Ремонт/Брак)
        if old_status == 'VIBROSTAND' and new_status not in ['TECH_CONTROL_1_1', 'TECH_CONTROL_1_2', 'REPAIR', 'DEFECT']:
             return False, "После вибростенда устройство должно идти только на Тех. контроль (ОТК)."

        return True, ""

    @staticmethod
    def can_accept_device(workplace_type: str, device_status: str) -> Tuple[bool, str]:
        """
        Проверка: может ли данный пост принять устройство с текущим статусом.
        Пример: Пост ASSEMBLY может принять только WAITING_ASSEMBLY.
        """
        if workplace_type == 'REPAIR':
            return True, "" # Ремонт принимает всё

        # Правило: Пост Х принимает устройство, если статус = WAITING_X
        expected_status = f"WAITING_{workplace_type}"
        
        # Исключение для PRE_PRODUCTION (может принимать WAITING_KITTING если KITTING пропущен)
        if workplace_type == 'PRE_PRODUCTION' and device_status == 'WAITING_KITTING':
            return True, ""

        if device_status != expected_status and device_status != workplace_type:
            return False, f"Устройство в статусе {device_status}. Пост {workplace_type} ожидает {expected_status}."

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
