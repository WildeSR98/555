import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
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
        self.setWindowTitle('Проверка спецификации')
        self.setFixedWidth(500)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Заголовок
        header_layout = QHBoxLayout()
        title_icon = QLabel("📋")
        title_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(title_icon)
        
        title_text = QLabel("Принятие в работу")
        title_text.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(title_text)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Инфо-блок (Форма)
        form_frame = QFrame()
        form_frame.setObjectName("formFrame")
        form_frame.setStyleSheet(f"""
            #formFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 15px;
            }}
            QLabel {{ color: {COLORS['text_secondary']}; font-weight: 500; }}
            QLineEdit {{ background-color: {COLORS['bg_input']}; color: white; border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px; }}
        """)
        
        form_layout = QFormLayout(form_frame)
        form_layout.setVerticalSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Отрисовка данных проекта
        project_name = QLineEdit(f"{self.project.name} ({self.project.code})")
        project_name.setReadOnly(True)
        project_name.setStyleSheet("background-color: transparent; border: none; font-weight: bold; font-size: 14px; color: white;")
        form_layout.addRow("Проект:", project_name)

        # Состав партии
        count = len(self.devices)
        sns = ", ".join([d.serial_number for d in self.devices[:3]])
        if count > 3:
            sns += f" ... и еще {count-3}"
        
        batch_info = QLabel(f"{count} шт. ({sns})")
        batch_info.setWordWrap(True)
        batch_info.setStyleSheet(f"color: {COLORS['text_primary']};")
        form_layout.addRow("Партия:", batch_info)

        # Ссылка на спеку
        if self.project.spec_link:
            self.link_btn = QPushButton("📄 Открыть документацию")
            self.link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.link_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['bg_elevated']};
                    color: {COLORS['accent']};
                    border: 1px solid {COLORS['accent']};
                    font-weight: bold;
                    padding: 8px;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: {COLORS['accent']}; color: white; }}
            """)
            self.link_btn.clicked.connect(self._open_spec)
            form_layout.addRow("Спецификация:", self.link_btn)
        else:
            no_link = QLabel("❌ Ссылка не задана")
            no_link.setStyleSheet(f"color: {COLORS['error']}; font-style: italic;")
            form_layout.addRow("Спецификация:", no_link)

        main_layout.addWidget(form_frame)

        # Поле ввода кода
        code_group = QVBoxLayout()
        code_label = QLabel("Проверочный код из спецификации:")
        code_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 13px;")
        code_group.addWidget(code_label)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Введите код подтверждения...")
        self.code_input.setMinimumHeight(50)
        self.code_input.setFont(QFont('Segoe UI', 18, QFont.Weight.Bold))
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_input']};
                border: 2px solid {COLORS['border']};
                border-radius: 10px;
                color: {COLORS['accent']};
                padding: 5px 15px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)
        self.code_input.setFocus()
        self.code_input.returnPressed.connect(self._verify_and_accept)
        code_group.addWidget(self.code_input)
        
        main_layout.addLayout(code_group)

        # Кнопки управления
        buttons = QHBoxLayout()
        
        close_btn = QPushButton("Отмена")
        close_btn.setProperty("class", "secondary")
        close_btn.setMinimumHeight(40)
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)

        self.confirm_btn = QPushButton("✅ Принять в работу")
        self.confirm_btn.setMinimumHeight(40)
        self.confirm_btn.setMinimumWidth(220)
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: #16a34a; }}
        """)
        self.confirm_btn.clicked.connect(self._verify_and_accept)
        buttons.addWidget(self.confirm_btn)

        main_layout.addLayout(buttons)

    def _open_spec(self):
        if self.project.spec_link:
            webbrowser.open(self.project.spec_link)

    def _verify_and_accept(self):
        input_code = self.code_input.text().strip()
        
        if not self.project.spec_code:
            QMessageBox.warning(self, "Ошибка проекта", 
                "Для этого проекта не задан проверочный код в базе данных.\n"
                "Обратитесь к администратору или менеджеру проекта.")
            return

        if input_code == self.project.spec_code:
            self.success = True
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", 
                "Неверный проверочный код!\n"
                "Смена статуса отклонена. Проверьте данные в спецификации.")
            self.code_input.selectAll()
            self.code_input.setFocus()
