"""
Вкладка Дашборд — обзор рабочих мест и активных сессий.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QGridLayout, QPushButton, QLineEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont

from ..database import get_session
from ..models import Workplace, WorkSession, Device, WorkLog
from .styles import COLORS, DEVICE_STATUS_COLORS


class DashboardLoadWorker(QObject):
    """Рабочий для фоновой загрузки данных дашборда."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            from sqlalchemy import func
            from datetime import datetime, timedelta
            session = get_session()

            data = {}

            # 1. Сводка
            data['total'] = session.query(Device).count()
            
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            data['completed_today'] = session.query(WorkLog).filter(
                WorkLog.action == 'COMPLETED',
                WorkLog.created_at >= today_start
            ).count()

            data['defects'] = session.query(Device).filter(Device.status == 'DEFECT').count()
            data['active_sessions_count'] = session.query(WorkSession).filter(WorkSession.is_active == True).count()

            # 2. Рабочие места
            workplaces = session.query(Workplace).filter(
                Workplace.is_active == True
            ).order_by(Workplace.order).all()

            data['workplaces'] = []
            for wp in workplaces:
                active = session.query(WorkSession).filter(
                    WorkSession.workplace_id == wp.id,
                    WorkSession.is_active == True
                ).count()
                
                data['workplaces'].append({
                    'name': wp.name,
                    'type_display': wp.type_display,
                    'pool_text': f'Пул ({wp.pool_limit})' if wp.is_pool else '—',
                    'status_text': f'🟢 {active} работн.' if active > 0 else '⚪ Свободно'
                })

            # 3. Активные сессии
            sessions = session.query(WorkSession).filter(
                WorkSession.is_active == True
            ).all()

            data['sessions'] = []
            for sess in sessions:
                # Длительность
                duration = '?'
                if sess.started_at:
                    delta = datetime.now() - sess.started_at
                    mins = int(delta.total_seconds() // 60)
                    duration = f'{mins // 60}ч {mins % 60}м' if mins >= 60 else f'{mins}м'

                data['sessions'].append({
                    'worker_name': sess.worker.full_name if sess.worker else '?',
                    'wp_name': sess.workplace.name if sess.workplace else '?',
                    'start_time': sess.started_at.strftime('%H:%M') if sess.started_at else '?',
                    'duration': duration
                })

            # 4. Последние 8 действий (Activity Feed)
            recent_logs = session.query(WorkLog).order_by(
                WorkLog.created_at.desc()
            ).limit(8).all()
            data['recent_logs'] = []
            for log in recent_logs:
                data['recent_logs'].append({
                    'worker': log.worker.full_name if log.worker else '?',
                    'action': log.action_display,
                    'sn': log.serial_number or '—',
                    'time': log.created_at.strftime('%H:%M') if log.created_at else '?',
                    'action_raw': log.action,
                })

            session.close()
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class DashboardTab(QWidget):
    """Вкладка Дашборд."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.thread = None
        self.worker = None
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
        hdr_wp = self.workplaces_table.horizontalHeader()
        hdr_wp.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Название
        hdr_wp.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Тип
        hdr_wp.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Пул
        hdr_wp.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Статус
        
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
        hdr_sess = self.sessions_table.horizontalHeader()
        hdr_sess.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Работник
        hdr_sess.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Рабочее место
        hdr_sess.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Начало
        hdr_sess.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Длительность
        
        self.sessions_table.setAlternatingRowColors(True)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sessions_table.verticalHeader().setVisible(False)
        right.addWidget(self.sessions_table)
        content.addLayout(right, stretch=1)

        layout.addLayout(content)

        # Activity Feed
        feed_title = QLabel('⚡ Последние действия')
        feed_title.setStyleSheet('font-size: 16px; font-weight: 600; margin-top: 4px;')
        layout.addWidget(feed_title)

        self.feed_list = QListWidget()
        self.feed_list.setMaximumHeight(180)
        self.feed_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QListWidget::item {{ padding: 6px 12px; border-bottom: 1px solid {COLORS['border']}; }}
            QListWidget::item:last-child {{ border-bottom: none; }}
        """)
        layout.addWidget(self.feed_list)

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
        """Запуск фонового обновления данных дашборда."""
        # Проверка, не запущен ли уже поток
        if hasattr(self, 'thread') and self.thread is not None:
            try:
                if self.thread.isRunning():
                    return
            except RuntimeError:
                # Объект потока был удален на стороне C++, сбрасываем ссылку
                self.thread = None

        self.thread = QThread()
        self.worker = DashboardLoadWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_data_loaded)
        self.worker.error.connect(self._on_load_error)
        
        # Очистка потока после завершения
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: setattr(self, 'thread', None))

        self.thread.start()

    def _on_data_loaded(self, data: dict) -> None:
        """Отрисовка полученных данных."""
        # 1. Карточки
        self._update_card_value(self.card_total, str(data['total']))
        self._update_card_value(self.card_today, str(data['completed_today']))
        self._update_card_value(self.card_defects, str(data['defects']))
        self._update_card_value(self.card_sessions, str(data['active_sessions_count']))

        # 2. Таблица рабочих мест
        self.workplaces_table.setRowCount(len(data['workplaces']))
        for i, wp in enumerate(data['workplaces']):
            self.workplaces_table.setItem(i, 0, QTableWidgetItem(wp['name']))
            self.workplaces_table.setItem(i, 1, QTableWidgetItem(wp['type_display']))
            self.workplaces_table.setItem(i, 2, QTableWidgetItem(wp['pool_text']))
            self.workplaces_table.setItem(i, 3, QTableWidgetItem(wp['status_text']))

        # 3. Таблица сессий
        self.sessions_table.setRowCount(len(data['sessions']))
        for i, sess in enumerate(data['sessions']):
            self.sessions_table.setItem(i, 0, QTableWidgetItem(sess['worker_name']))
            self.sessions_table.setItem(i, 1, QTableWidgetItem(sess['wp_name']))
            self.sessions_table.setItem(i, 2, QTableWidgetItem(sess['start_time']))
            self.sessions_table.setItem(i, 3, QTableWidgetItem(sess['duration']))

        # 4. Activity Feed
        action_icons = {
            'COMPLETED': '✅', 'SCAN_IN': '🟦', 'DEFECT': '🔴',
            'WAITING_PARTS': '🟡', 'REASSIGNED': '🔄', 'CANCEL_ACTION': '⏪',
            'MAKE_SEMIFINISHED': '🔧',
        }
        action_colors = {
            'COMPLETED':        '#22c55e',
            'SCAN_IN':          '#818cf8',
            'DEFECT':           '#ef4444',
            'MAKE_SEMIFINISHED':'#f59e0b',
            'CANCEL_ACTION':    '#94a3b8',
            'REASSIGNED':       '#06b6d4',
        }
        from PyQt6.QtGui import QColor
        self.feed_list.clear()
        for log in data.get('recent_logs', []):
            icon = action_icons.get(log['action_raw'], '●')
            text = f"{icon}  {log['time']}  {log['worker']} — {log['action']}  [{log['sn']}]"
            item = QListWidgetItem(text)
            color = action_colors.get(log['action_raw'], COLORS['text_secondary'])
            item.setForeground(QColor(color))
            self.feed_list.addItem(item)
        if not data.get('recent_logs'):
            self.feed_list.addItem('Нет действий')

    def _on_load_error(self, error_msg: str) -> None:
        print(f'Dashboard refresh error: {error_msg}')
