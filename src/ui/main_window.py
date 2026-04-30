"""
Главное окно приложения Production Manager.
Tab Widget с вкладками: Дашборд, Проекты, Конвейер, Сканирование, Статус SN, Аналитика.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QMenuBar,
    QMenu, QMessageBox, QHBoxLayout, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont

from ..database import test_connection
from ..models import User
from .styles import get_main_stylesheet, COLORS
from .dashboard_tab import DashboardTab
from .projects_tab import ProjectsTab
from .pipeline_tab import PipelineTab
from .scan_tab import ScanTab
from .device_status_tab import DeviceStatusTab
from .analytics_tab import AnalyticsTab
from .sn_pool_tab import SNPoolTab
from .admin_tab import AdminPanelTab, PasswordVerifyDialog
from .archive_tab import ArchiveTab
from .route_configs_tab import RouteConfigsTab


class MainWindow(QMainWindow):
    """Главное окно Production Manager."""

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        self.setWindowTitle(f'Production Manager — {self.user.full_name}')
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)
        self.setStyleSheet(get_main_stylesheet())

        # Меню
        self._create_menu()

        # Центральный виджет — Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Вкладки
        self.tabs.addTab(DashboardTab(self.user), '🏭  Дашборд')
        self.tabs.addTab(ProjectsTab(self.user), '📋  Проекты')
        self.tabs.addTab(PipelineTab(self.user), '🔧  Конвейер')
        self.tabs.addTab(ScanTab(self.user), '📱  Сканирование')
        self.tabs.addTab(DeviceStatusTab(self.user), '🔍  Статус SN')
        self.tabs.addTab(SNPoolTab(), '🔢  Пул SN')
        self.tabs.addTab(AnalyticsTab(self.user), '📊  Аналитика')
        self.tabs.addTab(ArchiveTab(self.user), '📦  Архив')
        self.tabs.addTab(RouteConfigsTab(self.user), '📋  Маршруты')

        self.admin_tab_index = -1
        if self.user.role in [User.ROLE_ADMIN, User.ROLE_MANAGER, User.ROLE_SHOP_MANAGER] or self.user.is_superuser:
            self.admin_tab_index = self.tabs.addTab(AdminPanelTab(self.user), '⚙️ Управление персоналом')

        # Обработчик смены вкладок: защита админ-панели
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.previous_tab_index = 0

        self.setCentralWidget(self.tabs)

        # Строка состояния
        self._create_status_bar()

    def _on_tab_changed(self, index: int) -> None:
        """Перехват смены вкладки для проверки пароля админа."""
        if index == self.admin_tab_index:
            dialog = PasswordVerifyDialog(self.user, self)
            if dialog.exec() == dialog.DialogCode.Accepted:
                self.previous_tab_index = index
            else:
                self.tabs.blockSignals(True)
                self.tabs.setCurrentIndex(self.previous_tab_index)
                self.tabs.blockSignals(False)
        else:
            self.previous_tab_index = index

    def _create_menu(self) -> None:
        """Создание меню."""
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu('Файл')

        logout_action = QAction('Выйти из аккаунта', self)
        logout_action.triggered.connect(self._logout)
        file_menu.addAction(logout_action)

        file_menu.addSeparator()

        exit_action = QAction('Выход', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Вид
        view_menu = menubar.addMenu('Вид')

        tabs_names = ['Дашборд', 'Проекты', 'Конвейер', 'Сканирование', 'Статус SN', 'Пул SN', 'Аналитика', 'Архив', 'Маршруты']
        for i, tab_name in enumerate(tabs_names):
            action = QAction(tab_name, self)
            action.setData(i)
            action.triggered.connect(lambda checked, idx=i: self.tabs.setCurrentIndex(idx))
            view_menu.addAction(action)

        # Справка
        help_menu = menubar.addMenu('Справка')

        about_action = QAction('О программе', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_status_bar(self) -> None:
        """Создание строки состояния."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # БД
        success, db_msg = test_connection()
        if success:
            db_label = QLabel(f'✓ БД: {db_msg}')
            db_label.setStyleSheet(f'color: {COLORS["success"]}; padding: 0 8px;')
        else:
            db_label = QLabel(f'✗ БД: {db_msg[:40]}')
            db_label.setStyleSheet(f'color: {COLORS["error"]}; padding: 0 8px;')
        status_bar.addWidget(db_label)

        # Пользователь
        user_label = QLabel(f'👤 {self.user.full_name} ({self.user.role_display})')
        user_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; padding: 0 8px;')
        status_bar.addPermanentWidget(user_label)

    def _logout(self) -> None:
        """Выход из аккаунта."""
        reply = QMessageBox.question(
            self, 'Выход',
            'Вы уверены, что хотите выйти из аккаунта?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
            # Перезапуск с окном логина
            from .login_dialog import LoginDialog
            import sys
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            dialog = LoginDialog()
            if dialog.exec() == dialog.DialogCode.Accepted:
                user = dialog.get_user()
                if user:
                    self.__class__(user).show()

    def _show_about(self) -> None:
        """Окно 'О программе'."""
        QMessageBox.about(
            self,
            'О программе',
            '<h2>Production Manager</h2>'
            '<p>Версия 1.0.0</p>'
            '<p>Система управления производственным конвейером.</p>'
            '<p>Компоненты: PyQt6, SQLAlchemy, matplotlib</p>'
            '<hr>'
            '<p><i>© 2026 PR DEP</i></p>'
        )
