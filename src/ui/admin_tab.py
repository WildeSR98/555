"""
Панель администратора для управления персоналом.
Позволяет создавать, редактировать и блокировать учетные записи сотрудников.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QLineEdit, QComboBox, QFormLayout, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from datetime import datetime

from ..database import get_session
from ..models import User
from .styles import COLORS

ROLE_CHOICES = [
    ('WORKER', 'Работник производства'),
    ('EMPLOYEE', 'Сотрудник'),
    ('MANAGER', 'Менеджер'),
    ('ADMIN', 'Администратор'),
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
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel('⚙️ Управление персоналом')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
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
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

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

    def refresh_data(self):
        try:
            session = get_session()
            users = session.query(User).order_by(User.id).all()

            self.table.setRowCount(len(users))

            for i, u in enumerate(users):
                # ID
                id_item = QTableWidgetItem(str(u.id))
                id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 0, id_item)

                # Логин
                self.table.setItem(i, 1, QTableWidgetItem(u.username))

                # ФИО
                self.table.setItem(i, 2, QTableWidgetItem(f"{u.first_name or ''} {u.last_name or ''}".strip() or '—'))

                # Роль
                self.table.setItem(i, 3, QTableWidgetItem(u.role_display))

                # Статус — цветной виджет
                status_widget = QWidget()
                sl = QHBoxLayout(status_widget)
                sl.setContentsMargins(8, 2, 8, 2)
                status_lbl = QLabel()
                if u.is_active:
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
                btn_edit.clicked.connect(lambda checked, uid=u.id: self._edit_user(uid))
                al.addWidget(btn_edit)

                toggle_text = 'Заблокировать' if u.is_active else 'Разблокировать'
                toggle_color = COLORS['error'] if u.is_active else COLORS['success']
                btn_toggle = QPushButton(toggle_text)
                btn_toggle.setMinimumHeight(26)
                btn_toggle.setStyleSheet(f"""
                    background-color: {toggle_color};
                    color: white; border-radius: 4px; border: none;
                    padding: 4px 12px; font-size: 11px; font-weight: bold;
                """)
                btn_toggle.clicked.connect(lambda checked, uid=u.id: self._toggle_active(uid))
                al.addWidget(btn_toggle)

                self.table.setCellWidget(i, 5, actions_widget)

            # Высота строк
            self.table.resizeRowsToContents()
            session.close()
        except Exception as e:
            print(f"AdminPanel error: {e}")

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
