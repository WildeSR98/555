"""
Вкладка Дашборд — обзор рабочих мест и активных сессий.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QGridLayout, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ..database import get_session
from ..models import Workplace, WorkSession, Device, WorkLog
from .styles import COLORS, DEVICE_STATUS_COLORS


class DashboardTab(QWidget):
    """Вкладка Дашборд."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()
        self.refresh_data()

        # Авто-обновление каждые 30 сек
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(30000)

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel('🏭 Дашборд')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton('⟳ Обновить')
        refresh_btn.setProperty('class', 'secondary')
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Сводные карточки
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(12)

        self.card_total = self._create_summary_card('Всего устройств', '0', COLORS['accent'])
        self.card_today = self._create_summary_card('Завершено сегодня', '0', COLORS['success'])
        self.card_defects = self._create_summary_card('В браке', '0', COLORS['error'])
        self.card_sessions = self._create_summary_card('Активные сессии', '0', COLORS['info'])

        self.cards_layout.addWidget(self.card_total)
        self.cards_layout.addWidget(self.card_today)
        self.cards_layout.addWidget(self.card_defects)
        self.cards_layout.addWidget(self.card_sessions)
        layout.addLayout(self.cards_layout)

        # Две колонки: Рабочие места | Активные сессии
        content = QHBoxLayout()
        content.setSpacing(16)

        # Левая колонка — Рабочие места
        left = QVBoxLayout()
        wp_header = QHBoxLayout()
        wp_title = QLabel('📋 Рабочие места')
        wp_title.setStyleSheet('font-size: 16px; font-weight: 600;')
        wp_header.addWidget(wp_title)
        wp_header.addStretch()
        left.addLayout(wp_header)

        self.workplaces_table = QTableWidget()
        self.workplaces_table.setColumnCount(4)
        self.workplaces_table.setHorizontalHeaderLabels(['Название', 'Тип', 'Пул', 'Статус'])
        self.workplaces_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.workplaces_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.workplaces_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.workplaces_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.workplaces_table.setAlternatingRowColors(True)
        self.workplaces_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.workplaces_table.verticalHeader().setVisible(False)
        left.addWidget(self.workplaces_table)
        content.addLayout(left, stretch=1)

        # Правая колонка — Активные сессии
        right = QVBoxLayout()
        sess_title = QLabel('⚡ Активные сессии')
        sess_title.setStyleSheet('font-size: 16px; font-weight: 600;')
        right.addWidget(sess_title)

        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(4)
        self.sessions_table.setHorizontalHeaderLabels(['Работник', 'Рабочее место', 'Начало', 'Длительность'])
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sessions_table.setAlternatingRowColors(True)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sessions_table.verticalHeader().setVisible(False)
        right.addWidget(self.sessions_table)
        content.addLayout(right, stretch=1)

        layout.addLayout(content)

    def _create_summary_card(self, title: str, value: str, color: str) -> QFrame:
        """Создание сводной карточки."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-top: 3px solid {color};
                border-radius: 10px;
                padding: 16px;
                min-width: 160px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(4)

        value_label = QLabel(value)
        value_label.setObjectName('cardValue')
        value_label.setStyleSheet(f'font-size: 32px; font-weight: bold; color: {color};')
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f'font-size: 12px; color: {COLORS["text_secondary"]};')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        return card

    def _update_card_value(self, card: QFrame, value: str) -> None:
        """Обновить значение сводной карточки."""
        label = card.findChild(QLabel, 'cardValue')
        if label:
            label.setText(value)

    def refresh_data(self) -> None:
        """Обновление данных дашборда."""
        try:
            session = get_session()

            # Сводные данные
            from sqlalchemy import func
            from datetime import datetime, timedelta

            total = session.query(Device).count()
            self._update_card_value(self.card_total, str(total))

            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            completed_today = session.query(WorkLog).filter(
                WorkLog.action == 'COMPLETED',
                WorkLog.created_at >= today_start
            ).count()
            self._update_card_value(self.card_today, str(completed_today))

            defects = session.query(Device).filter(Device.status == 'DEFECT').count()
            self._update_card_value(self.card_defects, str(defects))

            active_sessions = session.query(WorkSession).filter(WorkSession.is_active == True).count()
            self._update_card_value(self.card_sessions, str(active_sessions))

            # Рабочие места
            workplaces = session.query(Workplace).filter(
                Workplace.is_active == True
            ).order_by(Workplace.order).all()

            self.workplaces_table.setRowCount(len(workplaces))
            for i, wp in enumerate(workplaces):
                self.workplaces_table.setItem(i, 0, QTableWidgetItem(wp.name))
                self.workplaces_table.setItem(i, 1, QTableWidgetItem(wp.type_display))

                pool_text = f'Пул ({wp.pool_limit})' if wp.is_pool else '—'
                self.workplaces_table.setItem(i, 2, QTableWidgetItem(pool_text))

                active = session.query(WorkSession).filter(
                    WorkSession.workplace_id == wp.id,
                    WorkSession.is_active == True
                ).count()
                status_text = f'🟢 {active} работн.' if active > 0 else '⚪ Свободно'
                self.workplaces_table.setItem(i, 3, QTableWidgetItem(status_text))

            # Активные сессии
            sessions = session.query(WorkSession).filter(
                WorkSession.is_active == True
            ).all()

            self.sessions_table.setRowCount(len(sessions))
            for i, sess in enumerate(sessions):
                worker_name = sess.worker.full_name if sess.worker else '?'
                self.sessions_table.setItem(i, 0, QTableWidgetItem(worker_name))

                wp_name = sess.workplace.name if sess.workplace else '?'
                self.sessions_table.setItem(i, 1, QTableWidgetItem(wp_name))

                start = sess.started_at.strftime('%H:%M') if sess.started_at else '?'
                self.sessions_table.setItem(i, 2, QTableWidgetItem(start))

                if sess.started_at:
                    from datetime import datetime
                    delta = datetime.now() - sess.started_at
                    mins = int(delta.total_seconds() // 60)
                    duration = f'{mins // 60}ч {mins % 60}м' if mins >= 60 else f'{mins}м'
                else:
                    duration = '?'
                self.sessions_table.setItem(i, 3, QTableWidgetItem(duration))

            session.close()
        except Exception as e:
            print(f'Dashboard refresh error: {e}')
