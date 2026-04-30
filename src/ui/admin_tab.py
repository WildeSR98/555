"""
Панель администратора для управления персоналом.
Позволяет создавать, редактировать и блокировать учетные записи сотрудников.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QLineEdit, QComboBox, QFormLayout, QMessageBox, QFrame,
    QTabWidget, QTextEdit, QCheckBox, QSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor
from datetime import datetime

from ..database import get_session
from ..models import User, SystemConfig
from .styles import COLORS
import os, re, json

ROLE_CHOICES = [
    (User.ROLE_WORKER, 'Работник производства'),
    (User.ROLE_EMPLOYEE, 'Сотрудник'),
    (User.ROLE_SHOP_MANAGER, 'Начальник цеха'),
    (User.ROLE_MANAGER, 'Менеджер'),
    (User.ROLE_ADMIN, 'Администратор'),
]

DIALOG_STYLE = f"""
    QDialog {{ background-color: {COLORS['bg_surface']}; }}
    QLabel {{ color: {COLORS['text_primary']}; }}
    QLineEdit, QComboBox {{
        background-color: {COLORS['bg_input']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        padding: 8px;
        min-height: 20px;
    }}
    QPushButton {{
        background-color: {COLORS['bg_elevated']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        padding: 8px 16px;
        min-height: 20px;
    }}
"""


class AdminLoadWorker(QObject):
    """Рабочий для фоновой загрузки списка пользователей."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            session = get_session()
            users = session.query(User).order_by(User.id).all()
            
            data = []
            for u in users:
                data.append({
                    'id': u.id,
                    'username': u.username,
                    'full_name': f"{u.first_name or ''} {u.last_name or ''}".strip() or '—',
                    'role_display': u.role_display,
                    'is_active': u.is_active
                })
            
            session.close()
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class AddUserDialog(QDialog):
    """Диалог добавления нового пользователя."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Регистрация сотрудника')
        self.setMinimumWidth(380)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Логин или пинкод...')
        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText('Имя...')
        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText('Фамилия...')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Пароль...')
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.role_combo = QComboBox()
        for code, label in ROLE_CHOICES:
            self.role_combo.addItem(label, code)

        form_layout.addRow('Логин/Пин-код:', self.username_input)
        form_layout.addRow('Имя:', self.first_name_input)
        form_layout.addRow('Фамилия:', self.last_name_input)
        form_layout.addRow('Пароль:', self.password_input)
        form_layout.addRow('Роль:', self.role_combo)
        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton('💾 Сохранить')
        save_btn.setStyleSheet(f'background-color: {COLORS["accent"]}; color: white; border: none; font-weight: bold;')
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self) -> dict:
        return {
            'username': self.username_input.text().strip(),
            'first_name': self.first_name_input.text().strip(),
            'last_name': self.last_name_input.text().strip(),
            'password': self.password_input.text(),
            'role': self.role_combo.currentData()
        }


class EditUserDialog(QDialog):
    """Диалог редактирования существующего пользователя."""
    def __init__(self, user_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Редактирование: {user_data["username"]}')
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Информационный блок
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_elevated']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.addWidget(QLabel(f"<b>ID:</b> {user_data['id']}"))
        info_layout.addWidget(QLabel(f"<b>Логин:</b> {user_data['username']}"))
        info_layout.addWidget(QLabel(f"<b>Дата регистрации:</b> {user_data.get('date_joined', '—')}"))
        layout.addWidget(info_frame)

        form = QFormLayout()
        form.setSpacing(10)

        self.first_name_input = QLineEdit(user_data.get('first_name', ''))
        self.last_name_input = QLineEdit(user_data.get('last_name', ''))

        self.role_combo = QComboBox()
        for code, label in ROLE_CHOICES:
            self.role_combo.addItem(label, code)
        # Установить текущую роль
        for i, (code, _) in enumerate(ROLE_CHOICES):
            if code == user_data.get('role'):
                self.role_combo.setCurrentIndex(i)
                break

        form.addRow('Имя:', self.first_name_input)
        form.addRow('Фамилия:', self.last_name_input)
        form.addRow('Роль:', self.role_combo)
        layout.addLayout(form)

        # Секция сброса пароля
        pwd_label = QLabel('Новый пароль (оставьте пустым, если не менять):')
        pwd_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 11px; margin-top: 8px;')
        layout.addWidget(pwd_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Новый пароль...')
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton('💾 Сохранить изменения')
        save_btn.setStyleSheet(f'background-color: {COLORS["accent"]}; color: white; border: none; font-weight: bold;')
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self) -> dict:
        return {
            'first_name': self.first_name_input.text().strip(),
            'last_name': self.last_name_input.text().strip(),
            'role': self.role_combo.currentData(),
            'new_password': self.password_input.text(),
        }


class PasswordVerifyDialog(QDialog):
    """Окно проверки пароля перед входом в панель."""
    def __init__(self, current_user: User, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.setWindowTitle('Требуется авторизация')
        self.setFixedSize(320, 200)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel('Для доступа к управлению персоналом\nвведите ваш пароль еще раз:')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.returnPressed.connect(self.verify)
        layout.addWidget(self.pwd_input)

        self.error_lbl = QLabel('')
        self.error_lbl.setStyleSheet(f'color: {COLORS["error"]}; font-size: 11px;')
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_lbl)

        btn = QPushButton('Подтвердить')
        btn.setStyleSheet(f'background-color: {COLORS["accent"]}; color: white; border: none; font-weight: bold;')
        btn.clicked.connect(self.verify)
        layout.addWidget(btn)

    def verify(self):
        pwd = self.pwd_input.text()
        if self.current_user.check_password(pwd):
            self.accept()
        else:
            self.error_lbl.setText('Неверный пароль')


class AdminPanelTab(QWidget):
    """Вкладка панели администратора."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.thread = None
        self.worker = None
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel('⚙️ Управление')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        subtitle = QLabel('Персонал и системные настройки')
        subtitle.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 13px;')
        layout.addWidget(subtitle)

        # Суб-вкладки
        self.sub_tabs = QTabWidget()

        # 1. Сотрудники
        staff_widget = self._build_staff_tab()
        self.sub_tabs.addTab(staff_widget, '👥 Сотрудники')

        # 2. Логи ошибок (только ADMIN/ROOT)
        if self.user.role in (User.ROLE_ADMIN, User.ROLE_ROOT) or self.user.is_superuser:
            logs_widget = self._build_logs_tab()
            self.sub_tabs.addTab(logs_widget, '📋 Логи ошибок')

        # 3. Системные настройки (только ROOT)
        if self.user.role == User.ROLE_ROOT or self.user.is_superuser:
            settings_widget = self._build_settings_tab()
            self.sub_tabs.addTab(settings_widget, '🔧 Системные настройки')

        layout.addWidget(self.sub_tabs)

    # ── Staff tab ────────────────────────────────────────────────────────────
    def _build_staff_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)

        header = QHBoxLayout()
        header.addStretch()

        btn_refresh = QPushButton('⟳ Обновить')
        btn_refresh.setProperty('class', 'secondary')
        btn_refresh.clicked.connect(self.refresh_data)
        header.addWidget(btn_refresh)

        btn_add = QPushButton('➕ Добавить сотрудника')
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: white; border: none; border-radius: 6px;
                padding: 10px 20px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #16a34a; }}
        """)
        btn_add.clicked.connect(self._add_user)
        header.addWidget(btn_add)
        layout.addLayout(header)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            'ID', 'Логин / Пин', 'Имя Фамилия', 'Роль', 'Статус', 'Действия'
        ])

        # Растяжение колонок для читаемости
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Логин
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)          # ФИО
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Роль
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Статус
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Действия

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_surface']};
                gridline-color: {COLORS['border']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_elevated']};
                color: {COLORS['text_secondary']};
                padding: 8px;
                border: none;
                border-right: 1px solid {COLORS['border']};
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.table)
        return w

    # ── Logs tab ────────────────────────────────────────────────────────────
    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)

        ctrl = QHBoxLayout()
        from PyQt6.QtWidgets import QComboBox as _CB
        self._log_level = _CB()
        self._log_level.addItems(['🔴 ERROR', '🟡 WARNING', '🟢 INFO', '📋 Все'])
        ctrl.addWidget(QLabel('Уровень:'))
        ctrl.addWidget(self._log_level)

        self._log_search = QLineEdit()
        self._log_search.setPlaceholderText('🔍 Поиск...')
        ctrl.addWidget(self._log_search)

        reload_btn = QPushButton('⟳ Обновить')
        reload_btn.clicked.connect(self._load_logs)
        ctrl.addWidget(reload_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._log_table = QTableWidget()
        self._log_table.setColumnCount(4)
        self._log_table.setHorizontalHeaderLabels(['Дата/Время', 'Уровень', 'Компонент', 'Сообщение'])
        self._log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.setAlternatingRowColors(True)
        layout.addWidget(self._log_table)

        self._load_logs()
        return w

    def _load_logs(self) -> None:
        from ..logger import LOG_FILE
        level_map = {'ERROR': ['ERROR', 'CRITICAL'], 'WARNING': ['WARNING', 'ERROR', 'CRITICAL'],
                     'INFO': ['INFO', 'WARNING', 'ERROR', 'CRITICAL'], 'ALL': None}
        level_txt = self._log_level.currentText().split()[-1]
        allowed = level_map.get(level_txt)
        search = self._log_search.text().lower().strip() if hasattr(self, '_log_search') else ''

        rows = []
        pat = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| ([^|]+)\| (.*)')
        try:
            with open(LOG_FILE, encoding='utf-8', errors='replace') as f:
                for line in f:
                    m = pat.match(line.rstrip())
                    if not m:
                        # строка не соответствует формату — пропускаем
                        continue
                    dt, lvl, comp, msg = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
                    if allowed and lvl not in allowed:
                        continue
                    if search and search not in msg.lower() and search not in comp.lower():
                        continue
                    rows.append((dt, lvl, comp, msg))
        except (FileNotFoundError, PermissionError):
            rows = []
        except Exception:
            rows = []

        rows = rows[-200:]  # последние 200
        level_colors = {'ERROR': '#ef4444', 'CRITICAL': '#dc2626', 'WARNING': '#ca8a04', 'INFO': '#818cf8'}

        self._log_table.setRowCount(len(rows))
        for i, (dt, lvl, comp, msg) in enumerate(rows):
            self._log_table.setItem(i, 0, QTableWidgetItem(dt))
            lvl_item = QTableWidgetItem(lvl)
            lvl_item.setForeground(QColor(level_colors.get(lvl, COLORS['text_secondary'])))
            self._log_table.setItem(i, 1, lvl_item)
            self._log_table.setItem(i, 2, QTableWidgetItem(comp))
            self._log_table.setItem(i, 3, QTableWidgetItem(msg))

    # ── Settings tab ────────────────────────────────────────────────────────
    SETTING_ROLES = [
        ('ADMIN', 'Администратор'),
        ('MANAGER', 'Менеджер'),
        ('SHOP_MANAGER', 'Начальник цеха'),
        ('EMPLOYEE', 'Сотрудник'),
        ('WORKER', 'Работник'),
    ]

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)

        title = QLabel('🔧 Системные настройки')
        title.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(title)

        subtitle = QLabel('Определяет привилегии ролей на производстве. Только для ROOT.')
        subtitle.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 12px;')
        layout.addWidget(subtitle)

        self._settings_table = QTableWidget()
        self._settings_table.setColumnCount(3)
        self._settings_table.setHorizontalHeaderLabels(['Роль', 'Обход маршрута', 'Обход кулдауна (5 мин)'])
        self._settings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._settings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._settings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._settings_table.verticalHeader().setVisible(False)
        self._settings_table.setRowCount(len(self.SETTING_ROLES))

        self._route_cbs = {}
        self._cool_cbs = {}

        for row, (role_key, role_label) in enumerate(self.SETTING_ROLES):
            self._settings_table.setItem(row, 0, QTableWidgetItem(role_label))
            for col, store in [(1, self._route_cbs), (2, self._cool_cbs)]:
                cb = QCheckBox()
                cw = QWidget()
                cl = QHBoxLayout(cw)
                cl.addWidget(cb)
                cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.setContentsMargins(0, 0, 0, 0)
                self._settings_table.setCellWidget(row, col, cw)
                store[role_key] = cb

        layout.addWidget(self._settings_table)

        btn_bar = QHBoxLayout()
        save_btn = QPushButton('💾 Сохранить настройки')
        save_btn.setStyleSheet(f'background:{COLORS["accent"]}; color:white; border:none; border-radius:4px; padding:8px 20px; font-weight:bold;')
        save_btn.clicked.connect(self._save_settings)
        btn_bar.addWidget(save_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)
        layout.addStretch()

        self._load_settings()
        return w

    def _load_settings(self) -> None:
        try:
            session = get_session()
            route_cfg = session.query(SystemConfig).filter(SystemConfig.key == 'route_bypass_roles').first()
            cool_cfg  = session.query(SystemConfig).filter(SystemConfig.key == 'cooldown_bypass_roles').first()
            session.close()

            route_roles = json.loads(route_cfg.value) if route_cfg and route_cfg.value else []
            cool_roles  = json.loads(cool_cfg.value)  if cool_cfg  and cool_cfg.value  else []

            for role_key, _ in self.SETTING_ROLES:
                if role_key in self._route_cbs:
                    self._route_cbs[role_key].setChecked(role_key in route_roles)
                if role_key in self._cool_cbs:
                    self._cool_cbs[role_key].setChecked(role_key in cool_roles)
        except Exception as e:
            print(f'Settings load error: {e}')

    def _save_settings(self) -> None:
        route_roles = [k for k, _ in self.SETTING_ROLES if self._route_cbs.get(k) and self._route_cbs[k].isChecked()]
        cool_roles  = [k for k, _ in self.SETTING_ROLES if self._cool_cbs.get(k)  and self._cool_cbs[k].isChecked()]
        try:
            from datetime import datetime as _dt
            session = get_session()
            for key, val in [('route_bypass_roles', route_roles), ('cooldown_bypass_roles', cool_roles)]:
                cfg = session.query(SystemConfig).filter(SystemConfig.key == key).first()
                if cfg:
                    cfg.value = json.dumps(val)
                    cfg.updated_at = _dt.now()
                else:
                    session.add(SystemConfig(key=key, value=json.dumps(val), updated_at=_dt.now()))
            session.commit()
            session.close()
            QMessageBox.information(self, 'Сохранено', 'Настройки сохранены.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def refresh_data(self):
        """Запуск фоновой загрузки пользователей."""
        # Проверка, не запущен ли уже поток
        if hasattr(self, 'thread') and self.thread is not None:
            try:
                if self.thread.isRunning():
                    return
            except RuntimeError:
                # Объект потока был удален на стороне C++, сбрасываем ссылку
                self.thread = None

        self.thread = QThread()
        self.worker = AdminLoadWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_data_loaded)
        self.worker.error.connect(self._on_load_error)
        
        # Очистка потока после завершения
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: setattr(self, 'thread', None))

        self.thread.start()

    def _on_data_loaded(self, users_data: list):
        """Отрисовка полученных данных пользователей."""
        self.table.setRowCount(len(users_data))

        for i, u in enumerate(users_data):
            # ID
            id_item = QTableWidgetItem(str(u['id']))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, id_item)

            # Логин
            self.table.setItem(i, 1, QTableWidgetItem(u['username']))

            # ФИО
            self.table.setItem(i, 2, QTableWidgetItem(u['full_name']))

            # Роль
            self.table.setItem(i, 3, QTableWidgetItem(u['role_display']))

            # Статус — цветной виджет
            status_widget = QWidget()
            sl = QHBoxLayout(status_widget)
            sl.setContentsMargins(8, 2, 8, 2)
            status_lbl = QLabel()
            if u['is_active']:
                status_lbl.setText('Активен')
                status_lbl.setStyleSheet(f"""
                    background-color: {COLORS['success']};
                    color: white; border-radius: 4px;
                    padding: 4px 10px; font-weight: bold; font-size: 11px;
                """)
            else:
                status_lbl.setText('Заблокирован')
                status_lbl.setStyleSheet(f"""
                    background-color: {COLORS['error']};
                    color: white; border-radius: 4px;
                    padding: 4px 10px; font-weight: bold; font-size: 11px;
                """)
            sl.addWidget(status_lbl)
            self.table.setCellWidget(i, 4, status_widget)

            # Кнопки действий
            actions_widget = QWidget()
            al = QHBoxLayout(actions_widget)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(6)

            btn_edit = QPushButton('Изменить')
            btn_edit.setMinimumHeight(26)
            btn_edit.setStyleSheet(f"""
                background-color: {COLORS['accent']};
                color: white; border-radius: 4px; border: none;
                padding: 4px 12px; font-size: 11px; font-weight: bold;
            """)
            btn_edit.clicked.connect(lambda checked, uid=u['id']: self._edit_user(uid))
            al.addWidget(btn_edit)

            toggle_text = 'Заблокировать' if u['is_active'] else 'Разблокировать'
            toggle_color = COLORS['error'] if u['is_active'] else COLORS['success']
            btn_toggle = QPushButton(toggle_text)
            btn_toggle.setMinimumHeight(26)
            btn_toggle.setStyleSheet(f"""
                background-color: {toggle_color};
                color: white; border-radius: 4px; border: none;
                padding: 4px 12px; font-size: 11px; font-weight: bold;
            """)
            btn_toggle.clicked.connect(lambda checked, uid=u['id']: self._toggle_active(uid))
            al.addWidget(btn_toggle)

            self.table.setCellWidget(i, 5, actions_widget)

        # Высота строк
        self.table.resizeRowsToContents()

    def _on_load_error(self, error_msg: str):
        print(f"AdminPanel error: {error_msg}")

    def _add_user(self):
        dialog = AddUserDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['username'] or not data['password']:
                QMessageBox.warning(self, 'Ошибка', 'Логин и пароль обязательны!')
                return

            try:
                session = get_session()
                exists = session.query(User).filter(User.username == data['username']).first()
                if exists:
                    QMessageBox.warning(self, 'Ошибка', 'Сотрудник с таким логином уже существует.')
                    session.close()
                    return

                new_user = User(
                    username=data['username'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    role=data['role'],
                    is_active=True,
                    date_joined=datetime.now()
                )
                new_user.set_password(data['password'])

                session.add(new_user)
                session.commit()
                session.close()
                self.refresh_data()
                QMessageBox.information(self, 'Успех', f'Сотрудник "{data["username"]}" успешно создан.')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка БД', str(e))

    def _edit_user(self, user_id: int):
        try:
            session = get_session()
            u = session.query(User).get(user_id)
            if not u:
                session.close()
                return

            user_data = {
                'id': u.id,
                'username': u.username,
                'first_name': u.first_name or '',
                'last_name': u.last_name or '',
                'role': u.role,
                'date_joined': u.date_joined.strftime('%d.%m.%Y %H:%M') if u.date_joined else '—',
            }
            session.close()

            dialog = EditUserDialog(user_data, self)
            if dialog.exec():
                changes = dialog.get_data()
                session = get_session()
                u = session.query(User).get(user_id)

                u.first_name = changes['first_name']
                u.last_name = changes['last_name']
                u.role = changes['role']

                if changes['new_password']:
                    u.set_password(changes['new_password'])

                session.commit()
                session.close()
                self.refresh_data()
                QMessageBox.information(self, 'Успех', f'Данные сотрудника "{u.username}" обновлены.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _toggle_active(self, user_id: int):
        if user_id == self.user.id:
            QMessageBox.warning(self, 'Ошибка', 'Нельзя заблокировать самого себя!')
            return

        try:
            session = get_session()
            u = session.query(User).get(user_id)
            new_state = not u.is_active
            action = 'разблокирован' if new_state else 'заблокирован'

            reply = QMessageBox.question(
                self, 'Подтверждение',
                f'Сотрудник "{u.username}" будет {action}. Продолжить?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                u.is_active = new_state
                session.commit()
            session.close()
            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
