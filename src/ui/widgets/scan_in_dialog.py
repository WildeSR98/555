import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ..styles import COLORS

class ScanInDialog(QDialog):
    """Окно принятия устройства в работу с проверкой кода из спеки."""

    def __init__(self, devices, project, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.project = project
        self.success = False
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle('Принятие в работу')
        self.setFixedWidth(450)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Инфо о проекте и устройствах
        info_frame = QFrame()
        info_frame.setStyleSheet(f"background-color: {COLORS['bg_surface']}; border-radius: 8px; border: 1px solid {COLORS['border']};")
        info_layout = QVBoxLayout(info_frame)
        
        project_label = QLabel(f"<b>Проект:</b> {self.project.name} ({self.project.code})")
        info_layout.addWidget(project_label)
        
        count = len(self.devices)
        sns = ", ".join([d.serial_number for d in self.devices[:3]])
        if count > 3:
            sns += f" ... и еще {count-3}"
        
        devices_label = QLabel(f"<b>Устройства ({count} шт):</b><br>{sns}")
        devices_label.setWordWrap(True)
        info_layout.addWidget(devices_label)
        
        layout.addWidget(info_frame)

        # Статус
        status_label = QLabel("Статус: <span style='color: #3b82f6; font-weight: bold;'>В РАБОТУ</span>")
        status_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(status_label)

        # Ссылка на спеку
        if self.project.spec_link:
            link_btn = QPushButton("📄 Открыть спецификацию (Browser)")
            link_btn.setMinimumHeight(40)
            link_btn.setStyleSheet(f"background-color: {COLORS['accent']}; color: white; font-weight: bold;")
            link_btn.clicked.connect(self._open_spec)
            layout.addWidget(link_btn)
        else:
            no_link = QLabel("⚠️ Ссылка на спецификацию не задана в проекте")
            no_link.setStyleSheet("color: #ef4444; font-style: italic;")
            layout.addWidget(no_link)

        # Ввод кода
        code_layout = QVBoxLayout()
        code_label = QLabel("Введите проверочный код из спецификации:")
        code_label.setStyleSheet("font-weight: 600;")
        code_layout.addWidget(code_label)
        
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Код подтверждения...")
        self.code_input.setMinimumHeight(45)
        self.code_input.setFont(QFont('Segoe UI', 16))
        self.code_input.setFocus()
        self.code_input.returnPressed.connect(self._verify_and_accept)
        code_layout.addWidget(self.code_input)
        layout.addLayout(code_layout)

        # Кнопки
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.accept_btn = QPushButton("Начать работу")
        self.accept_btn.setMinimumHeight(40)
        self.accept_btn.setMinimumWidth(200)
        self.accept_btn.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold;")
        self.accept_btn.clicked.connect(self._verify_and_accept)
        btn_layout.addWidget(self.accept_btn)
        
        layout.addLayout(btn_layout)

    def _open_spec(self):
        if self.project.spec_link:
            webbrowser.open(self.project.spec_link)

    def _verify_and_accept(self):
        input_code = self.code_input.text().strip()
        
        # Если код в проекте не задан, разрешаем вход (или блокируем?)
        # Судя по требованиям, он фиксированный и хранится в спеке.
        if not self.project.spec_code:
            QMessageBox.warning(self, "Ошибка", "В настройках проекта не задан проверочный код. Обратитесь к администратору.")
            return

        if input_code == self.project.spec_code:
            self.success = True
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", "Неверный проверочный код! Проверьте данные в спецификации.")
            self.code_input.selectAll()
            self.code_input.setFocus()
