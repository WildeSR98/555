"""
Диалог входа в систему.
Проверяет учётные данные через Django-совместимую проверку паролей.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpacerItem, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from ..database import get_session, test_connection
from ..models import User
from .styles import get_login_stylesheet, COLORS


class LoginDialog(QDialog):
    """Окно входа в систему."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user: User | None = None
        self._setup_ui()
        self._check_db_connection()

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        self.setWindowTitle('Production Manager — Вход')
        self.setFixedSize(420, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(get_login_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Иконка / логотип
        icon_label = QLabel('🏭')
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFont(QFont('Segoe UI', 48))
        layout.addWidget(icon_label)

        layout.addSpacing(16)

        # Заголовок
        title = QLabel('Production Manager')
        title.setObjectName('loginTitle')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(4)

        # Подзаголовок
        subtitle = QLabel('Управление производством')
        subtitle.setObjectName('loginSubtitle')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(32)

        # Поле логина
        username_label = QLabel('Имя пользователя')
        username_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 12px; font-weight: 600;')
        layout.addWidget(username_label)
        layout.addSpacing(6)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Введите логин...')
        self.username_input.setObjectName('usernameInput')
        layout.addWidget(self.username_input)

        layout.addSpacing(16)

        # Поле пароля
        password_label = QLabel('Пароль')
        password_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 12px; font-weight: 600;')
        layout.addWidget(password_label)
        layout.addSpacing(6)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Введите пароль...')
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName('passwordInput')
        self.password_input.returnPressed.connect(self._on_login)
        layout.addWidget(self.password_input)

        layout.addSpacing(8)

        # Ошибка
        self.error_label = QLabel('')
        self.error_label.setObjectName('errorLabel')
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        layout.addSpacing(16)

        # Кнопка входа
        self.login_btn = QPushButton('Войти')
        self.login_btn.setObjectName('loginBtn')
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        layout.addStretch()

        # Статус БД
        self.db_status = QLabel('')
        self.db_status.setObjectName('dbStatus')
        self.db_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.db_status)

    def _check_db_connection(self) -> None:
        """Проверка подключения к БД."""
        success, message = test_connection()
        if success:
            self.db_status.setText(f'✓ Подключено: {message}')
            self.db_status.setStyleSheet(f'color: {COLORS["success"]}; font-size: 11px;')
        else:
            self.db_status.setText(f'✗ Ошибка БД: {message}')
            self.db_status.setStyleSheet(f'color: {COLORS["error"]}; font-size: 11px;')
            self.login_btn.setEnabled(False)

    def _on_login(self) -> None:
        """Обработка нажатия кнопки 'Войти'."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText('Заполните все поля')
            return

        self.error_label.setText('')
        self.login_btn.setEnabled(False)
        self.login_btn.setText('Вход...')

        try:
            session = get_session()
            user = session.query(User).filter(
                User.username == username,
                User.is_active == True
            ).first()

            if user and user.check_password(password):
                self.current_user = user
                session.close()
                self.accept()
            else:
                self.error_label.setText('Неверное имя пользователя или пароль')
                self.login_btn.setEnabled(True)
                self.login_btn.setText('Войти')
                session.close()
        except Exception as e:
            self.error_label.setText(f'Ошибка: {str(e)[:60]}')
            self.login_btn.setEnabled(True)
            self.login_btn.setText('Войти')

    def get_user(self) -> User | None:
        """Получить авторизованного пользователя."""
        return self.current_user
