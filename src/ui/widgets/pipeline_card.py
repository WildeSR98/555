"""
Карточка этапа конвейера.
Отображает название этапа и количество устройств.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from ..styles import COLORS, DEVICE_STATUS_COLORS


class PipelineCard(QFrame):
    """Карточка этапа конвейера."""

    clicked = pyqtSignal(str)  # Сигнал: код статуса

    def __init__(self, status_code: str, label: str, count: int = 0, parent=None):
        super().__init__(parent)
        self.status_code = status_code
        self._count = count
        self._setup_ui(label, count)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self, label: str, count: int) -> None:
        """Настройка интерфейса карточки."""
        color = DEVICE_STATUS_COLORS.get(self.status_code, '#6c757d')

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-left: 4px solid {color};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame:hover {{
                background-color: {COLORS['bg_hover']};
                border-color: {color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Количество устройств (большое число)
        self.count_label = QLabel(str(count))
        self.count_label.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {color};
        """)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # Название этапа
        name_label = QLabel(label)
        name_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {COLORS['text_secondary']};
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        self.setMinimumWidth(120)
        self.setMaximumWidth(160)
        self.setMinimumHeight(90)

    def update_count(self, count: int) -> None:
        """Обновить количество устройств."""
        self._count = count
        self.count_label.setText(str(count))

    def mousePressEvent(self, event) -> None:
        """Обработка клика по карточке."""
        self.clicked.emit(self.status_code)
        super().mousePressEvent(event)
