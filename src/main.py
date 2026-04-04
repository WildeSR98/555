"""
Production Manager — точка входа.
Запуск приложения: python src/main.py
"""

import sys
import os

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt

from src.ui.login_dialog import LoginDialog
from src.ui.main_window import MainWindow


def main() -> None:
    """Главная функция запуска приложения."""
    # Включаем High DPI масштабирование
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'

    app = QApplication(sys.argv)
    app.setApplicationName('Production Manager')
    app.setOrganizationName('PR DEP')
    app.setApplicationVersion('1.0.0')

    # Шрифт по умолчанию
    font = QFont('Segoe UI', 10)
    app.setFont(font)

    # Иконка (если есть)
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Окно логина
    login = LoginDialog()
    if login.exec() != login.DialogCode.Accepted:
        sys.exit(0)

    user = login.get_user()
    if not user:
        sys.exit(0)

    # Главное окно
    window = MainWindow(user)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
