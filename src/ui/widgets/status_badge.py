"""
Виджет цветного статус-бейджа.
Используется для отображения статусов устройств, проектов, операций.
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt


class StatusBadge(QLabel):
    """Цветной бейдж статуса."""

    def __init__(self, text: str, color: str = '#6c757d', parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        """Установить цвет бейджа."""
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 3px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                min-width: 60px;
            }}
        """)

    def update_status(self, text: str, color: str) -> None:
        """Обновить текст и цвет бейджа."""
        self.setText(text)
        self.set_color(color)
