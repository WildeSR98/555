"""
SQLAlchemy ORM модели — зеркало Django-моделей из office-task-manager.
Работают с той же БД (SQLite / PostgreSQL).

ВАЖНО: таблицы Django используют префиксы app_name:
  - accounts_user
  - tasks_project, tasks_device, tasks_operation
  - production_workplace, production_worksession, production_worklog
  - auth_group
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date,
    ForeignKey, Table, MetaData
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# =============================================
# Django auth_group (стандартная таблица)
# =============================================

class Group(Base):
    __tablename__ = 'auth_group'

    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)

    def __repr__(self) -> str:
        return self.name


# Таблица связи User <-> Group (Django стандарт)
user_groups_table = Table(
    'accounts_user_groups',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('accounts_user.id')),
    Column('group_id', Integer, ForeignKey('auth_group.id')),
)


# =============================================
# Accounts
# =============================================

class User(Base):
    """Пользователь системы (зеркало accounts.User)"""
    __tablename__ = 'accounts_user'

    id = Column(Integer, primary_key=True)
    password = Column(String(128), nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_superuser = Column(Boolean, default=False)
    username = Column(String(150), unique=True, nullable=False)
    first_name = Column(String(150), default='')
    last_name = Column(String(150), default='')
    email = Column(String(254), default='')
    is_staff = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    date_joined = Column(DateTime)
    role = Column(String(20), default='EMPLOYEE')
    phone = Column(String(20), default='')
    action_pin = Column(String(4), nullable=True)
    avatar = Column(String(100), nullable=True)

    # Relationships
    groups = relationship('Group', secondary=user_groups_table, backref='users')

    # Role choices
    ROLE_ADMIN = 'ADMIN'
    ROLE_MANAGER = 'MANAGER'
    ROLE_SHOP_MANAGER = 'SHOP_MANAGER'
    ROLE_EMPLOYEE = 'EMPLOYEE'
    ROLE_WORKER = 'WORKER'
    ROLE_ROOT = 'ROOT'  # Скрытая системная рольь, не отображается в UI

    ROLE_DISPLAY = {
        'ADMIN': 'Администратор',
        'MANAGER': 'Менеджер',
        'SHOP_MANAGER': 'Начальник цеха',
        'EMPLOYEE': 'Сотрудник',
        'WORKER': 'Работник производства',
    }

    @property
    def full_name(self) -> str:
        name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return name or self.username

    @property
    def role_display(self) -> str:
        return self.ROLE_DISPLAY.get(self.role, self.role)

    def check_password(self, raw_password: str) -> bool:
        """
        Проверка пароля Django (pbkdf2_sha256).
        Django формат: algorithm$iterations$salt$hash
        """
        import hashlib
        import base64

        if not self.password or '$' not in self.password:
            return False

        parts = self.password.split('$')
        if len(parts) != 4:
            return False

        algorithm, iterations, salt, stored_hash = parts
        iterations = int(iterations)

        if algorithm == 'pbkdf2_sha256':
            dk = hashlib.pbkdf2_hmac(
                'sha256',
                raw_password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations
            )
            computed_hash = base64.b64encode(dk).decode('ascii')
            return computed_hash == stored_hash

        return False

    def set_password(self, raw_password: str) -> None:
        """
        Установка пароля (pbkdf2_sha256).
        Формат Django: algorithm$iterations$salt$hash
        """
        import hashlib
        import base64
        import secrets

        algorithm = 'pbkdf2_sha256'
        iterations = 600000
        salt = secrets.token_urlsafe(16)
        
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            raw_password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        computed_hash = base64.b64encode(dk).decode('ascii')
        self.password = f"{algorithm}${iterations}${salt}${computed_hash}"

    def __repr__(self) -> str:
        return f"{self.full_name} ({self.role_display})"


# =============================================
# Tasks
# =============================================

class Project(Base):
    """Проект (зеркало tasks.Project)"""
    __tablename__ = 'tasks_project'

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default='')
    status = Column(String(50), default='PLANNING')
    manager_id = Column(Integer, ForeignKey('accounts_user.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    deadline = Column(Date, nullable=True)
    spec_link = Column(String(500), nullable=True)
    spec_code = Column(String(100), nullable=True)

    # Relationships
    manager = relationship('User', foreign_keys=[manager_id])
    devices = relationship('Device', back_populates='project', cascade='all, delete-orphan')

    STATUS_DISPLAY = {
        'PLANNING': 'Планирование',
        'ACTIVE': 'Активный',
        'ON_HOLD': 'Приостановлен',
        'COMPLETED': 'Завершён',
        'CANCELLED': 'Отменён',
    }

    STATUS_COLORS = {
        'PLANNING': '#6c757d',
        'ACTIVE': '#007bff',
        'ON_HOLD': '#ffc107',
        'COMPLETED': '#28a745',
        'CANCELLED': '#dc3545',
    }

    @property
    def status_display(self) -> str:
        return self.STATUS_DISPLAY.get(self.status, self.status)

    def __repr__(self) -> str:
        return f"{self.code} - {self.name}"


class DeviceModel(Base):
    """Пользовательские типы/модели устройств для генерации SN"""
    __tablename__ = 'tasks_devicemodel'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False) # e.g. 'TIOGA'
    name = Column(String(100), nullable=False)    # e.g. 'Tioga Type 4'
    sn_prefix = Column(String(50), nullable=False) # e.g. '60LXTRDC'

    def __repr__(self) -> str:
        return f"{self.category}: {self.name}"


class SerialNumber(Base):
    """Пул сгенерированных серийных номеров"""
    __tablename__ = 'tasks_serialnumber'

    id = Column(Integer, primary_key=True)
    sn = Column(String(100), unique=True, nullable=False, index=True)
    model_id = Column(Integer, ForeignKey('tasks_devicemodel.id'), nullable=False)
    is_used = Column(Boolean, default=False)
    device_id = Column(Integer, ForeignKey('tasks_device.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime)
    
    device_model = relationship('DeviceModel', backref='serial_numbers')

    def __repr__(self) -> str:
        return self.sn


class Device(Base):
    """Устройство (зеркало tasks.Device)"""
    __tablename__ = 'tasks_device'

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=True)
    project_id = Column(Integer, ForeignKey('tasks_project.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(200), nullable=False)
    serial_number = Column(String(100), default='', index=True)
    device_type = Column(String(20), default='COMPUTER')
    part_number = Column(String(100), default='', index=True)
    is_semifinished = Column(Boolean, default=False)
    location = Column(String(200), default='')
    current_worker_id = Column(Integer, ForeignKey('accounts_user.id', ondelete='SET NULL'), nullable=True)
    status = Column(String(50), default='WAITING_KITTING', index=True)
    description = Column(Text, default='')
    created_at = Column(DateTime, index=True)
    updated_at = Column(DateTime, index=True)

    # Relationships
    project = relationship('Project', back_populates='devices')
    current_worker = relationship('User', foreign_keys=[current_worker_id])
    operations = relationship('Operation', back_populates='device', cascade='all, delete-orphan')
    sn_record = relationship('SerialNumber', backref='device', uselist=False)

    DEVICE_TYPE_DISPLAY = {
        'COMPUTER': 'Компьютер', 'LAPTOP': 'Ноутбук', 'SERVER': 'Сервер',
        'PRINTER': 'Принтер', 'SCANNER': 'Сканер', 'ROUTER': 'Роутер',
        'SWITCH': 'Коммутатор', 'PHONE': 'Телефон', 'TABLET': 'Планшет',
        'PC': 'ПК', 'MONITOR': 'Монитор', 'TIOGA': 'Tioga',
        'JBOH': 'JBOH', 'JBOX': 'JBOX', 'SERVAL': 'Serval',
        'OCTOPUS': 'Octopus', 'RACK': 'Стойка', 'OTHER': 'Другое',
    }

    # Префиксы генерации серийных номеров
    SN_PREFIXES = {
        'PC': '60PCBRDS',
        'MONITOR': '60MSO4IC',
        'JBOH': '60LXH4DC',
        'JBOX': '50LXX4DC',
        'TIOGA': '60LXTRDC',
        'SERVAL': '60LXRLDC',
        'OCTOPUS': '60LXOPDS',
        'RACK': '60LXA4DS',
    }

    STATUS_DISPLAY = {
        'ACTIVE': 'Активно', 'INACTIVE': 'Неактивно',
        'MAINTENANCE': 'На обслуживании', 'BROKEN': 'Неисправно',
        'RETIRED': 'Списано',
        'WAITING_KITTING': 'Ожидание комплектовки',
        'PRE_PRODUCTION': 'Комплектовка',
        'WAITING_PRE_PRODUCTION': 'Ожидание комплектовки',
        'WAITING_ASSEMBLY': 'Ожидание сборки',
        'ASSEMBLY': 'Сборка',
        'WAITING_VIBROSTAND': 'Ожидание вибростенда',
        'VIBROSTAND': 'Вибростенд',
        'WAITING_TECH_CONTROL_1_1': 'Ожидание ОТК 1.1',
        'TECH_CONTROL_1_1': 'Тех. контроль 1.1',
        'WAITING_TECH_CONTROL_1_2': 'Ожидание ОТК 1.2',
        'TECH_CONTROL_1_2': 'Тех. контроль 1.2',
        'WAITING_FUNC_CONTROL': 'Ожидание функц. контроля',
        'FUNC_CONTROL': 'Функц. контроль',
        'WAITING_TECH_CONTROL_2_1': 'Ожидание ОТК 2.1',
        'TECH_CONTROL_2_1': 'Тех. контроль 2.1',
        'WAITING_TECH_CONTROL_2_2': 'Ожидание ОТК 2.2',
        'TECH_CONTROL_2_2': 'Тех. контроль 2.2',
        'QC_PASSED': 'Контроль пройден',
        'DEFECT': 'Брак', 'WAITING_PARTS': 'Ожидание запчастей',
        'WAITING_SOFTWARE': 'Ожидание ПО',
        'WAITING_PACKING': 'Ожидание упаковки',
        'PACKING': 'Упаковка', 
        'WAITING_ACCOUNTING': 'Ожидание учёта',
        'ACCOUNTING': 'Учёт',
        'WAITING_WAREHOUSE': 'Ожидание склада',
        'WAREHOUSE': 'Склад',
        'QC_PASSED': 'Склад (Завершено)',
    }

    STATUS_COLORS = {
        'WAITING_KITTING': '#94a3b8',
        'WAITING_PRE_PRODUCTION': '#94a3b8',
        'PRE_PRODUCTION': '#6c757d',
        'WAITING_ASSEMBLY': '#94a3b8',
        'ASSEMBLY': '#3b82f6',
        'WAITING_VIBROSTAND': '#94a3b8',
        'VIBROSTAND': '#06b6d4',
        'WAITING_TECH_CONTROL_1_1': '#94a3b8',
        'TECH_CONTROL_1_1': '#eab308', 
        'WAITING_TECH_CONTROL_1_2': '#94a3b8',
        'TECH_CONTROL_1_2': '#eab308',
        'WAITING_FUNC_CONTROL': '#94a3b8',
        'FUNC_CONTROL': '#f97316',
        'WAITING_TECH_CONTROL_2_1': '#94a3b8',
        'TECH_CONTROL_2_1': '#eab308', 
        'WAITING_TECH_CONTROL_2_2': '#94a3b8',
        'TECH_CONTROL_2_2': '#eab308',
        'WAITING_PACKING': '#94a3b8',
        'PACKING': '#14b8a6', 
        'WAITING_ACCOUNTING': '#94a3b8',
        'ACCOUNTING': '#8b5cf6',
        'QC_PASSED': '#22c55e',
        'DEFECT': '#ef4444',
        'WAITING_PARTS': '#f59e0b',
        'WAITING_SOFTWARE': '#f59e0b',
        'WAITING_WAREHOUSE': '#94a3b8',
        'WAREHOUSE': '#16a34a',
        'SHIPPED': '#059669',
        'ACTIVE': '#28a745', 'INACTIVE': '#6c757d',
        'MAINTENANCE': '#ffc107', 'BROKEN': '#dc3545', 'RETIRED': '#343a40',
    }

    # Порядок этапов конвейера
    PIPELINE_STAGES = [
        'WAITING_KITTING', 
        'WAITING_PRE_PRODUCTION', 'PRE_PRODUCTION', 
        'WAITING_ASSEMBLY', 'ASSEMBLY', 
        'WAITING_VIBROSTAND', 'VIBROSTAND',
        'WAITING_TECH_CONTROL_1_1', 'TECH_CONTROL_1_1',
        'WAITING_TECH_CONTROL_1_2', 'TECH_CONTROL_1_2',
        'WAITING_FUNC_CONTROL', 'FUNC_CONTROL',
        'WAITING_TECH_CONTROL_2_1', 'TECH_CONTROL_2_1',
        'WAITING_TECH_CONTROL_2_2', 'TECH_CONTROL_2_2',
        'WAITING_PACKING', 'PACKING', 
        'WAITING_ACCOUNTING', 'ACCOUNTING',
        'WAITING_WAREHOUSE', 'WAREHOUSE', 'QC_PASSED',
        'DEFECT', 'WAITING_PARTS', 'WAITING_SOFTWARE', 'SHIPPED'
    ]

    @property
    def status_display(self) -> str:
        return self.STATUS_DISPLAY.get(self.status, self.status)

    @property
    def device_type_display(self) -> str:
        return self.DEVICE_TYPE_DISPLAY.get(self.device_type, self.device_type)

    def __repr__(self) -> str:
        code_str = self.code if self.code else "NO_CODE"
        return f"{code_str} - {self.name}"


class Operation(Base):
    """Операция над устройством (зеркало tasks.Operation)"""
    __tablename__ = 'tasks_operation'

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=True)
    device_id = Column(Integer, ForeignKey('tasks_device.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default='')
    status = Column(String(20), default='PENDING')
    group_id = Column(Integer, ForeignKey('auth_group.id'), nullable=True)
    created_by_id = Column(Integer, ForeignKey('accounts_user.id'), nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    device = relationship('Device', back_populates='operations')
    group = relationship('Group')
    created_by = relationship('User', foreign_keys=[created_by_id])

    STATUS_DISPLAY = {
        'PENDING': 'Ожидает',
        'IN_PROGRESS': 'В работе',
        'COMPLETED': 'Завершена',
        'CANCELLED': 'Отменена',
    }

    STATUS_COLORS = {
        'PENDING': '#6c757d',
        'IN_PROGRESS': '#007bff',
        'COMPLETED': '#28a745',
        'CANCELLED': '#dc3545',
    }

    @property
    def status_display(self) -> str:
        return self.STATUS_DISPLAY.get(self.status, self.status)

    def __repr__(self) -> str:
        code_str = self.code if self.code else "NO_CODE"
        return f"{code_str} - {self.title}"


# =============================================
# Production
# =============================================

# Таблица связи Workplace <-> Groups
workplace_groups_table = Table(
    'production_workplace_allowed_groups',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('workplace_id', Integer, ForeignKey('production_workplace.id')),
    Column('group_id', Integer, ForeignKey('auth_group.id')),
)

# Таблица связи Workplace <-> Workplace (allowed_sources)
workplace_sources_table = Table(
    'production_workplace_allowed_sources',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('from_workplace_id', Integer, ForeignKey('production_workplace.id')),
    Column('to_workplace_id', Integer, ForeignKey('production_workplace.id')),
)


class Workplace(Base):
    """Рабочее место на производственной линии (зеркало production.Workplace)"""
    __tablename__ = 'production_workplace'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    workplace_type = Column(String(50), nullable=False)
    is_pool = Column(Boolean, default=False)
    pool_limit = Column(Integer, default=0)
    accepts_semifinished = Column(Boolean, default=False)
    restrict_same_worker = Column(Boolean, default=False)
    device_status_on_enter = Column(String(50), default='')
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Relationships
    allowed_groups = relationship('Group', secondary=workplace_groups_table)
    allowed_sources = relationship(
        'Workplace',
        secondary=workplace_sources_table,
        primaryjoin=id == workplace_sources_table.c.to_workplace_id,
        secondaryjoin=id == workplace_sources_table.c.from_workplace_id,
    )

    TYPE_DISPLAY = {
        'PRE_PRODUCTION': 'Комплектовка',
        'ASSEMBLY': 'Сборка', 'VIBROSTAND': 'Вибростенд',
        'TECH_CONTROL_1_1': 'Тех. контроль 1.1',
        'TECH_CONTROL_1_2': 'Тех. контроль 1.2',
        'TECH_CONTROL_2_1': 'Тех. контроль 2.1',
        'TECH_CONTROL_2_2': 'Тех. контроль 2.2',
        'FUNC_CONTROL': 'Функц. контроль',
        'PACKING': 'Упаковка', 'ACCOUNTING': 'Учёт',
        'REPAIR': 'Ремонтный стенд', 'WAITING_POOL': 'Пул ожидания',
    }

    @property
    def type_display(self) -> str:
        return self.TYPE_DISPLAY.get(self.workplace_type, self.workplace_type)

    def __repr__(self) -> str:
        return self.name


class WorkSession(Base):
    """Сессия работника на рабочем месте (зеркало production.WorkSession)"""
    __tablename__ = 'production_worksession'

    id = Column(Integer, primary_key=True)
    workplace_id = Column(Integer, ForeignKey('production_workplace.id'), nullable=False, index=True)
    worker_id = Column(Integer, ForeignKey('accounts_user.id'), nullable=False, index=True)
    started_at = Column(DateTime, index=True)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    # Relationships
    workplace = relationship('Workplace')
    worker = relationship('User')

    def __repr__(self) -> str:
        return f"{self.worker} @ {self.workplace}"


class WorkLog(Base):
    """Журнал производственных действий (зеркало production.WorkLog)"""
    __tablename__ = 'production_worklog'

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey('accounts_user.id', ondelete='SET NULL'), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey('production_worksession.id', ondelete='SET NULL'), nullable=True)
    workplace_id = Column(Integer, ForeignKey('production_workplace.id', ondelete='SET NULL'), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey('tasks_device.id', ondelete='SET NULL'), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('tasks_project.id', ondelete='SET NULL'), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)
    old_status = Column(String(50), default='')
    new_status = Column(String(50), default='')
    part_number = Column(String(100), default='')
    serial_number = Column(String(100), default='', index=True)
    missing_parts = Column(String(500), default='')
    defective_part_sn = Column(String(100), default='')
    notes = Column(Text, default='')
    created_at = Column(DateTime, index=True)

    # Relationships
    worker = relationship('User')
    session = relationship('WorkSession')
    workplace = relationship('Workplace')
    device = relationship('Device')
    project = relationship('Project')

    ACTION_DISPLAY = {
        'SCAN_IN': 'Взят в работу',
        'COMPLETED': 'Завершён',
        'MAKE_SEMIFINISHED': 'Сделать полуфабрикатом',
        'DEFECT': 'Отправлен в брак',
        'WAITING_PARTS': 'Ожидание запчастей',
        'WAITING_SOFTWARE': 'Ожидание ПО',
        'REASSIGNED': 'Передан другому',
        'KEPT': 'Оставлен у работника',
        'CANCEL_ACTION': 'Отмена операции',
        'ROUTE_CHANGE': 'Смена маршрута',
    }

    ACTION_COLORS = {
        'SCAN_IN': '#3b82f6',
        'COMPLETED': '#22c55e',
        'MAKE_SEMIFINISHED': '#8b5cf6',
        'DEFECT': '#ef4444',
        'WAITING_PARTS': '#f59e0b',
        'WAITING_SOFTWARE': '#f59e0b',
        'REASSIGNED': '#8b5cf6',
        'KEPT': '#6b7280',
        'CANCEL_ACTION': '#dc3545',
        'ROUTE_CHANGE': '#6366f1',
    }

    @property
    def action_display(self) -> str:
        return self.ACTION_DISPLAY.get(self.action, self.action)

    def __repr__(self) -> str:
        return f"{self.created_at} [{self.workplace}] SN:{self.serial_number} — {self.action_display}"


# =============================================
# Системные настройки (только для root)
# =============================================

class SystemConfig(Base):
    """Key-value хранилище системных настроек. Управляется только через root."""
    __tablename__ = 'pm_system_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"SystemConfig({self.key}={self.value})"


# =============================================
# Маршрутные листы (Route Configs)
# =============================================

# Упорядоченный список этапов конвейера для маршрутных листов
ROUTE_PIPELINE_STAGES = [
    ('KITTING',           'Комплектовка',       1),
    ('ASSEMBLY',          'Сборка',             2),
    ('VIBROSTAND',        'Вибростенд',         3),
    ('TECH_CONTROL_1_1',  'ОТК 1.1',            4),
    ('TECH_CONTROL_1_2',  'ОТК 1.2',            5),
    ('FUNC_CONTROL',      'Функц. контроль',    6),
    ('TECH_CONTROL_2_1',  'ОТК 2.1',            7),
    ('TECH_CONTROL_2_2',  'ОТК 2.2',            8),
    ('PACKING',           'Упаковка',           9),
    ('ACCOUNTING',        'Учёт',               10),
    ('WAREHOUSE',         'Склад',              11),
]


class RouteConfig(Base):
    """Конфигурация маршрута производства."""
    __tablename__ = 'pm_route_config'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(200), nullable=False)
    description  = Column(Text, default='')
    device_type  = Column(String(50), nullable=True)   # Привязка к типу устройства
    is_default   = Column(Boolean, default=False)      # Системный дефолтный, нельзя удалить
    created_at   = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey('accounts_user.id', ondelete='SET NULL'), nullable=True)

    # Relationships
    stages    = relationship('RouteConfigStage',  back_populates='route_config',
                             cascade='all, delete-orphan', order_by='RouteConfigStage.order_index')
    editors   = relationship('RouteConfigEditor', back_populates='route_config',
                             cascade='all, delete-orphan')
    created_by = relationship('User', foreign_keys=[created_by_id])

    def get_enabled_stages(self) -> list:
        """Список включённых этапов (ключи)."""
        return [s.stage_key for s in self.stages if s.is_enabled]

    def __repr__(self) -> str:
        return f"RouteConfig({self.id}: {self.name})"


class RouteConfigStage(Base):
    """Этап маршрута с флагом включения."""
    __tablename__ = 'pm_route_config_stage'

    id               = Column(Integer, primary_key=True, autoincrement=True)
    route_config_id  = Column(Integer, ForeignKey('pm_route_config.id', ondelete='CASCADE'), nullable=False)
    stage_key        = Column(String(50), nullable=False)   # напр. ASSEMBLY
    order_index      = Column(Integer, nullable=False)
    is_enabled       = Column(Boolean, default=True)
    label            = Column(String(100), nullable=True)   # кастомный ярлык (напр. «Комплектовка-доукомплектование»)
    timer_seconds     = Column(Integer, nullable=True)          # таймер этапа в секундах

    route_config = relationship('RouteConfig', back_populates='stages')

    def __repr__(self) -> str:
        flag = '✅' if self.is_enabled else '❌'
        return f"{self.order_index}. {flag} {self.stage_key}"


class RouteConfigEditor(Base):
    """Пользователь, получивший права на редактирование конкретного маршрута."""
    __tablename__ = 'pm_route_config_editor'

    id               = Column(Integer, primary_key=True, autoincrement=True)
    route_config_id  = Column(Integer, ForeignKey('pm_route_config.id', ondelete='CASCADE'), nullable=False)
    user_id          = Column(Integer, ForeignKey('accounts_user.id', ondelete='CASCADE'), nullable=False)

    route_config = relationship('RouteConfig', back_populates='editors')
    user         = relationship('User', foreign_keys=[user_id])


class ProjectRoute(Base):
    """Назначенный маршрут производства для проекта."""
    __tablename__ = 'pm_project_route'

    id               = Column(Integer, primary_key=True, autoincrement=True)
    project_id       = Column(Integer, ForeignKey('tasks_project.id', ondelete='CASCADE'),
                              nullable=False, unique=True)
    route_config_id  = Column(Integer, ForeignKey('pm_route_config.id', ondelete='SET NULL'), nullable=True)
    assigned_at      = Column(DateTime, nullable=True)
    assigned_by_id   = Column(Integer, ForeignKey('accounts_user.id', ondelete='SET NULL'), nullable=True)

    route_config = relationship('RouteConfig')
    assigned_by  = relationship('User', foreign_keys=[assigned_by_id])

    def __repr__(self) -> str:
        return f"ProjectRoute(project={self.project_id} → route={self.route_config_id})"


class DeviceCategory(Base):
    """Динамические категории устройств (перекрывают хардкодный Device.DEVICE_TYPE_DISPLAY)."""
    __tablename__ = 'pm_device_category'

    code         = Column(String(50), primary_key=True)   # Ключ тип. 'TIOGA', 'NEWCAT'
    display_name = Column(String(200), nullable=False)    # Отображаемое имя
    sn_prefix    = Column(String(50), nullable=True)      # Префикс SN
    sort_order   = Column(Integer, default=100)           # Порядок отображения

    def __repr__(self) -> str:
        return f"DeviceCategory({self.code}: {self.display_name})"


class ProjectRouteStage(Base):
    """Индивидуальный маршрут проекта по типу устройства.

    Перекрывает глобальный RouteConfig для конкретного проекта.
    Если записей нет — используется глобальный RouteConfig для данного device_type.
    """
    __tablename__ = 'pm_project_route_stage'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(Integer, ForeignKey('tasks_project.id', ondelete='CASCADE'), nullable=False)
    device_type = Column(String(50), nullable=False)
    stage_key   = Column(String(200), nullable=False)
    order_index = Column(Integer, nullable=False)
    is_enabled  = Column(Boolean, default=True)
    label         = Column(String(200), nullable=True)
    timer_seconds = Column(Integer, nullable=True)   # таймер этапа в секундах

    project = relationship('Project', backref='route_stages')

    def __repr__(self) -> str:
        return f"ProjectRouteStage(p={self.project_id} {self.device_type} {self.stage_key})"
