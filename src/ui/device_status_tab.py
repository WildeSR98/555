"""
Вкладка Статус SN — поиск устройства по серийному номеру и просмотр истории.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ..database import get_session
from ..models import Device, WorkLog
from .styles import COLORS, DEVICE_STATUS_COLORS


class DeviceStatusTab(QWidget):
    """Вкладка поиска статуса устройства по SN."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок
        title = QLabel('🔍 Статус устройства')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        layout.addWidget(title)

        # Поиск
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 20px;
            }}
        """)
        search_layout = QHBoxLayout(search_frame)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Введите серийный номер (SN)...')
        self.search_input.setMinimumHeight(44)
        self.search_input.setFont(QFont('Segoe UI', 15))
        self.search_input.returnPressed.connect(self._search)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton('🔍 Найти')
        search_btn.setMinimumHeight(44)
        search_btn.setMinimumWidth(120)
        search_btn.clicked.connect(self._search)
        search_layout.addWidget(search_btn)

        layout.addWidget(search_frame)

        # Результаты — карточка устройства
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 20px;
            }}
        """)
        self.result_frame.setVisible(False)

        result_layout = QVBoxLayout(self.result_frame)

        self.device_header = QLabel('')
        self.device_header.setStyleSheet('font-size: 18px; font-weight: bold;')
        result_layout.addWidget(self.device_header)

        self.device_details = QLabel('')
        self.device_details.setStyleSheet(f'font-size: 13px; color: {COLORS["text_secondary"]}; line-height: 1.6;')
        self.device_details.setWordWrap(True)
        result_layout.addWidget(self.device_details)

        layout.addWidget(self.result_frame)

        # Лог не найден
        self.not_found_label = QLabel('')
        self.not_found_label.setStyleSheet(f'font-size: 14px; color: {COLORS["error"]}; padding: 10px;')
        self.not_found_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.not_found_label.setVisible(False)
        layout.addWidget(self.not_found_label)

        # Таблица истории
        history_label = QLabel('📜 История действий')
        history_label.setStyleSheet('font-size: 16px; font-weight: 600;')
        self.history_header = history_label
        self.history_header.setVisible(False)
        layout.addWidget(history_label)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            'Дата/Время', 'Действие', 'Рабочее место', 'Работник', 'Статус →', 'Примечания'
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setVisible(False)
        layout.addWidget(self.history_table)

    def _search(self) -> None:
        """Поиск устройства по SN."""
        sn = self.search_input.text().strip()
        if not sn:
            return

        try:
            session = get_session()

            device = session.query(Device).filter(
                Device.serial_number == sn
            ).first()

            if not device:
                # Попробуем частичный поиск
                device = session.query(Device).filter(
                    Device.serial_number.contains(sn)
                ).first()

            if not device:
                self.result_frame.setVisible(False)
                self.history_table.setVisible(False)
                self.history_header.setVisible(False)
                self.not_found_label.setText(f'Устройство с SN "{sn}" не найдено')
                self.not_found_label.setVisible(True)
                session.close()
                return

            self.not_found_label.setVisible(False)

            # Карточка устройства
            status_color = DEVICE_STATUS_COLORS.get(device.status, '#6c757d')
            self.device_header.setText(
                f'📦 {device.name}  —  SN: {device.serial_number}'
            )
            self.device_details.setText(
                f'<b>Проект:</b> {device.project.name if device.project else "—"}  ·  '
                f'<b>Код:</b> {device.code or "—"}  ·  '
                f'<b>PN:</b> {device.part_number or "—"}<br>'
                f'<b>Тип:</b> {device.device_type_display}  ·  '
                f'<b>Статус:</b> <span style="color:{status_color}; font-weight:bold;">'
                f'{device.status_display}</span>  ·  '
                f'<b>Полуфабрикат:</b> {"Да" if device.is_semifinished else "Нет"}<br>'
                f'<b>Текущий работник:</b> '
                f'{device.current_worker.full_name if device.current_worker else "—"}  ·  '
                f'<b>Расположение:</b> {device.location or "—"}'
            )
            self.result_frame.setVisible(True)

            # История действий
            logs = session.query(WorkLog).filter(
                WorkLog.device_id == device.id
            ).order_by(WorkLog.created_at.desc()).limit(50).all()

            self.history_table.setRowCount(len(logs))
            for i, log in enumerate(logs):
                dt = log.created_at.strftime('%d.%m.%Y %H:%M') if log.created_at else '—'
                self.history_table.setItem(i, 0, QTableWidgetItem(dt))

                action_item = QTableWidgetItem(log.action_display)
                action_color = WorkLog.ACTION_COLORS.get(log.action, '#6b7280')
                action_item.setForeground(QColor(action_color))
                self.history_table.setItem(i, 1, action_item)

                self.history_table.setItem(i, 2, QTableWidgetItem(
                    log.workplace.name if log.workplace else '—'
                ))
                self.history_table.setItem(i, 3, QTableWidgetItem(
                    log.worker.full_name if log.worker else '—'
                ))

                status_text = f'{log.old_status} → {log.new_status}' if log.old_status else log.new_status
                self.history_table.setItem(i, 4, QTableWidgetItem(status_text))

                self.history_table.setItem(i, 5, QTableWidgetItem(log.notes or ''))

            self.history_table.setVisible(True)
            self.history_header.setVisible(True)
            session.close()

        except Exception as e:
            self.not_found_label.setText(f'Ошибка: {str(e)[:60]}')
            self.not_found_label.setVisible(True)
