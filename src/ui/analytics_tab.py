"""
Вкладка Аналитика — графики производственных показателей и контроль сотрудников.
Использует matplotlib для визуализации.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QTabWidget, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

from ..database import get_session
from ..models import Device, WorkLog, User, Workplace
from .styles import COLORS, DEVICE_STATUS_COLORS

# Попытка импорта matplotlib
try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except Exception as _mpl_err:
    HAS_MATPLOTLIB = False
    print(f"[analytics] matplotlib недоступен: {_mpl_err}")

from datetime import datetime, timedelta
from sqlalchemy import func

class AnalyticsTab(QWidget):
    """Вкладка Аналитика."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel('📊 Аналитика производства')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton('⟳ Обновить данные')
        refresh_btn.setProperty('class', 'secondary')
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background-color: {COLORS['bg_surface']};
                margin-top: 5px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['bg_surface']};
                color: {COLORS['accent']};
                border-bottom: 2px solid {COLORS['accent']};
            }}
        """)

        # Создаем вкладки
        self.tab_general = QWidget()
        self.tab_employee = QWidget()

        self._setup_general_tab()
        self._setup_employee_tab()

        self.tabs.addTab(self.tab_general, "📈 Общая сводка")
        self.tabs.addTab(self.tab_employee, "👤 По сотрудникам")

        layout.addWidget(self.tabs)

    def _setup_general_tab(self):
        """Интерфейс общей аналитики (графики)."""
        layout = QVBoxLayout(self.tab_general)
        layout.setContentsMargins(16, 16, 16, 16)
        
        if not HAS_MATPLOTLIB:
            no_mpl = QLabel('⚠️ matplotlib не установлен. Установите: pip install matplotlib')
            no_mpl.setStyleSheet(f'font-size: 14px; color: {COLORS["warning"]}; padding: 20px;')
            no_mpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_mpl)
            return

        # Сводные карточки
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(12)
        self.card_total = self._create_card('Всего устройств', '0', COLORS['accent'])
        self.card_completed = self._create_card('Завершено сегодня', '0', COLORS['success'])
        self.card_defects = self._create_card('В браке', '0', COLORS['error'])
        self.card_active = self._create_card('На линии', '0', COLORS['info'])
        self.cards_layout.addWidget(self.card_total)
        self.cards_layout.addWidget(self.card_completed)
        self.cards_layout.addWidget(self.card_defects)
        self.cards_layout.addWidget(self.card_active)
        layout.addLayout(self.cards_layout)

        # Графики в сетке 2x2
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea { border: none; }')

        charts_widget = QWidget()
        self.charts_grid = QGridLayout(charts_widget)
        self.charts_grid.setSpacing(16)

        self.fig_status = Figure(figsize=(5, 3.5), facecolor=COLORS['bg_surface'])
        self.canvas_status = FigureCanvasQTAgg(self.fig_status)
        self._wrap_chart(self.canvas_status, 'Устройства по статусам', 0, 0)

        self.fig_weekly = Figure(figsize=(5, 3.5), facecolor=COLORS['bg_surface'])
        self.canvas_weekly = FigureCanvasQTAgg(self.fig_weekly)
        self._wrap_chart(self.canvas_weekly, 'Завершено за неделю', 0, 1)

        self.fig_workers = Figure(figsize=(5, 3.5), facecolor=COLORS['bg_surface'])
        self.canvas_workers = FigureCanvasQTAgg(self.fig_workers)
        self._wrap_chart(self.canvas_workers, 'Топ работников', 1, 0)

        self.fig_workplaces = Figure(figsize=(5, 3.5), facecolor=COLORS['bg_surface'])
        self.canvas_workplaces = FigureCanvasQTAgg(self.fig_workplaces)
        self._wrap_chart(self.canvas_workplaces, 'Загрузка рабочих мест', 1, 1)

        scroll.setWidget(charts_widget)
        layout.addWidget(scroll)

    def _setup_employee_tab(self):
        """Интерфейс детальной статистики по сотруднику."""
        layout = QVBoxLayout(self.tab_employee)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Фильтры
        filter_layout = QHBoxLayout()

        self.emp_combo = QComboBox()
        self.emp_combo.setMinimumWidth(250)
        self.emp_combo.setMinimumHeight(36)
        filter_layout.addWidget(QLabel('Сотрудник:'))
        filter_layout.addWidget(self.emp_combo)

        self.period_combo = QComboBox()
        self.period_combo.setMinimumHeight(36)
        self.period_combo.addItems([
            'Сегодня', 'За неделю', 'За месяц', 'За всё время'
        ])
        filter_layout.addWidget(QLabel('  Период:'))
        filter_layout.addWidget(self.period_combo)

        filter_layout.addStretch()

        apply_btn = QPushButton('Запросить отчёт')
        apply_btn.setMinimumHeight(36)
        apply_btn.clicked.connect(self._refresh_employee_data)
        filter_layout.addWidget(apply_btn)

        layout.addLayout(filter_layout)

        # Сводные карточки по сотруднику
        self.emp_cards_layout = QHBoxLayout()
        self.emp_cards_layout.setSpacing(12)
        self.emp_card_done = self._create_card('Выполнено этапов', '0', COLORS['success'])
        self.emp_card_defect = self._create_card('Обнаружено брака', '0', COLORS['error'])
        self.emp_card_in_prog = self._create_card('Взято в работу (SCAN_IN)', '0', COLORS['accent'])
        self.emp_cards_layout.addWidget(self.emp_card_done)
        self.emp_cards_layout.addWidget(self.emp_card_defect)
        self.emp_cards_layout.addWidget(self.emp_card_in_prog)
        layout.addLayout(self.emp_cards_layout)

        # Таблица истории
        history_label = QLabel('Хронология действий (Логи)')
        history_label.setStyleSheet(f'font-size: 16px; font-weight: bold; margin-top: 10px;')
        layout.addWidget(history_label)

        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(5)
        self.table_logs.setHorizontalHeaderLabels([
            'Время', 'Действие', 'SN устройства', 'Проект', 'Рабочее место'
        ])
        hdr = self.table_logs.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Время
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Действие
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # SN
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)           # Проект
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)           # Рабочее место
        self.table_logs.setAlternatingRowColors(True)
        self.table_logs.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_logs.verticalHeader().setVisible(False)
        layout.addWidget(self.table_logs)

    def _create_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-top: 3px solid {color};
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)
        card_layout.setContentsMargins(12, 8, 12, 8)

        val = QLabel(value)
        val.setObjectName('cardValue')
        val.setStyleSheet(f'font-size: 28px; font-weight: bold; color: {color};')
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(val)

        lbl = QLabel(title)
        lbl.setStyleSheet(f'font-size: 11px; color: {COLORS["text_secondary"]};')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl)
        return card

    def _update_card(self, card: QFrame, value: str) -> None:
        label = card.findChild(QLabel, 'cardValue')
        if label:
            label.setText(value)

    def _wrap_chart(self, canvas, title: str, row: int, col: int) -> None:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)

        lbl = QLabel(title)
        lbl.setStyleSheet(f'font-size: 14px; font-weight: 600; color: {COLORS["text_secondary"]};')
        frame_layout.addWidget(lbl)
        frame_layout.addWidget(canvas)

        self.charts_grid.addWidget(frame, row, col)

    def refresh_data(self) -> None:
        """Обновление данных при клике 'Обновить'."""
        self._refresh_general_data()
        self._load_workers_list()
        self._refresh_employee_data()

    def _load_workers_list(self):
        try:
            session = get_session()
            workers = session.query(User).order_by(User.username).all()
            
            # Сохраняем текущий выбор
            current_id = self.emp_combo.currentData()
            self.emp_combo.clear()
            
            idx_to_restore = 0
            for i, w in enumerate(workers):
                self.emp_combo.addItem(f'{w.full_name} ({w.username})', w.id)
                if current_id and w.id == current_id:
                    idx_to_restore = i
            
            self.emp_combo.setCurrentIndex(idx_to_restore)
            session.close()
        except Exception as e:
            print(f'Error loading workers: {e}')

    def _refresh_employee_data(self):
        worker_id = self.emp_combo.currentData()
        if not worker_id:
            return
            
        period_text = self.period_combo.currentText()
        now = datetime.now()
        start_date = None
        
        if period_text == 'Сегодня':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period_text == 'За неделю':
            start_date = now - timedelta(days=7)
        elif period_text == 'За месяц':
            start_date = now - timedelta(days=30)
        
        try:
            session = get_session()
            query = session.query(WorkLog).filter(WorkLog.worker_id == worker_id)
            if start_date:
                query = query.filter(WorkLog.created_at >= start_date)
            
            logs = query.order_by(WorkLog.created_at.desc()).all()
            
            completed_count = 0
            defect_count = 0
            scan_in_count = 0
            
            self.table_logs.setRowCount(len(logs))
            
            for i, log in enumerate(logs):
                # Подсчет статы
                if log.action == 'COMPLETED':
                    completed_count += 1
                elif log.action == 'DEFECT':
                    defect_count += 1
                elif log.action == 'SCAN_IN':
                    scan_in_count += 1
                
                # Заполнение таблицы
                self.table_logs.setItem(i, 0, QTableWidgetItem(log.created_at.strftime("%d.%m.%Y %H:%M:%S")))
                
                action_displays = {
                    'SCAN_IN': 'Взят в работу',
                    'COMPLETED': 'Завершён',
                    'IN_PROGRESS': 'В процессе',
                    'DEFECT': 'Брак',
                    'KEPT': 'Оставлен',
                    'MAKE_SEMIFINISHED': 'Отправлен в полуфабрикат'
                }
                disp_act = action_displays.get(log.action, log.action)
                self.table_logs.setItem(i, 1, QTableWidgetItem(disp_act))
                
                self.table_logs.setItem(i, 2, QTableWidgetItem(log.serial_number or ''))
                self.table_logs.setItem(i, 3, QTableWidgetItem(log.project.name if log.project else ''))
                self.table_logs.setItem(i, 4, QTableWidgetItem(log.workplace.name if log.workplace else ''))
            
            self._update_card(self.emp_card_done, str(completed_count))
            self._update_card(self.emp_card_defect, str(defect_count))
            self._update_card(self.emp_card_in_prog, str(scan_in_count))
            
            session.close()
        except Exception as e:
            print(f'Employee data error: {e}')

    def _refresh_general_data(self) -> None:
        """Обновление графиков."""
        if not HAS_MATPLOTLIB:
            return

        try:
            session = get_session()
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = now - timedelta(days=7)

            total = session.query(Device).count()
            self._update_card(self.card_total, str(total))

            completed = session.query(WorkLog).filter(
                WorkLog.action == 'COMPLETED',
                WorkLog.created_at >= today_start
            ).count()
            self._update_card(self.card_completed, str(completed))

            defects = session.query(Device).filter(Device.status == 'DEFECT').count()
            self._update_card(self.card_defects, str(defects))

            pipeline_statuses = Device.PIPELINE_STAGES
            on_line = session.query(Device).filter(
                Device.status.in_(pipeline_statuses)
            ).count()
            self._update_card(self.card_active, str(on_line))

            # ---- GRAPH 1 ----
            self.fig_status.clear()
            ax1 = self.fig_status.add_subplot(111)
            ax1.set_facecolor(COLORS['bg_surface'])

            status_counts = session.query(
                Device.status, func.count(Device.id)
            ).group_by(Device.status).all()

            if status_counts:
                labels = [Device.STATUS_DISPLAY.get(s, s) for s, _ in status_counts]
                sizes = [c for _, c in status_counts]
                colors = [DEVICE_STATUS_COLORS.get(s, '#6c757d') for s, _ in status_counts]
                wedges, texts, autotexts = ax1.pie(
                    sizes, labels=None, colors=colors,
                    autopct='%1.0f%%', startangle=90,
                    pctdistance=0.8, textprops={'color': COLORS['text_primary'], 'fontsize': 8}
                )
                ax1.legend(labels, loc='center left', bbox_to_anchor=(1, 0.5),
                           fontsize=7, facecolor=COLORS['bg_surface'],
                           edgecolor=COLORS['border'],
                           labelcolor=COLORS['text_secondary'])
                centre_circle = matplotlib.patches.Circle((0, 0), 0.55, fc=COLORS['bg_surface'])
                ax1.add_artist(centre_circle)
            else:
                ax1.text(0.5, 0.5, 'Нет данных', ha='center', va='center',
                         color=COLORS['text_muted'], fontsize=12, transform=ax1.transAxes)

            self.fig_status.tight_layout()
            self.canvas_status.draw()

            # ---- GRAPH 2 ----
            self.fig_weekly.clear()
            ax2 = self.fig_weekly.add_subplot(111)
            ax2.set_facecolor(COLORS['bg_surface'])

            weekly_data = {}
            logs = session.query(
                func.date(WorkLog.created_at).label('day'),
                func.count(WorkLog.id).label('cnt')
            ).filter(
                WorkLog.action == 'COMPLETED',
                WorkLog.created_at >= week_ago
            ).group_by('day').all()

            for log in logs:
                weekly_data[str(log.day)] = log.cnt

            days = []
            counts = []
            for i in range(7):
                d = (week_ago + timedelta(days=i)).date()
                days.append(d.strftime('%d.%m'))
                counts.append(weekly_data.get(str(d), 0))

            bars = ax2.bar(days, counts, color=COLORS['accent'])
            ax2.tick_params(colors=COLORS['text_secondary'], labelsize=8)
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['bottom'].set_color(COLORS['border'])
            ax2.spines['left'].set_color(COLORS['border'])
            ax2.set_ylabel('Кол-во', color=COLORS['text_secondary'], fontsize=9)

            self.fig_weekly.tight_layout()
            self.canvas_weekly.draw()

            # ---- GRAPH 3 ----
            self.fig_workers.clear()
            ax3 = self.fig_workers.add_subplot(111)
            ax3.set_facecolor(COLORS['bg_surface'])

            workers = session.query(
                User.first_name, User.last_name, User.username,
                func.count(WorkLog.id).label('cnt')
            ).join(WorkLog, WorkLog.worker_id == User.id).filter(
                WorkLog.action == 'COMPLETED',
                WorkLog.created_at >= week_ago
            ).group_by(User.id).order_by(func.count(WorkLog.id).desc()).limit(8).all()

            if workers:
                w_names = []
                w_counts = []
                for w in reversed(workers):
                    name = f'{w.first_name or ""} {w.last_name or ""}'.strip() or w.username
                    w_names.append(name[:15])
                    w_counts.append(w.cnt)
                ax3.barh(w_names, w_counts, color=COLORS['success'], height=0.6)
                ax3.tick_params(colors=COLORS['text_secondary'], labelsize=8)
            else:
                ax3.text(0.5, 0.5, 'Нет данных', ha='center', va='center',
                         color=COLORS['text_muted'], fontsize=12, transform=ax3.transAxes)

            ax3.spines['top'].set_visible(False)
            ax3.spines['right'].set_visible(False)
            ax3.spines['bottom'].set_color(COLORS['border'])
            ax3.spines['left'].set_color(COLORS['border'])

            self.fig_workers.tight_layout()
            self.canvas_workers.draw()

            # ---- GRAPH 4 ----
            self.fig_workplaces.clear()
            ax4 = self.fig_workplaces.add_subplot(111)
            ax4.set_facecolor(COLORS['bg_surface'])

            wp_stats = session.query(
                Workplace.name, func.count(WorkLog.id).label('cnt')
            ).join(WorkLog, WorkLog.workplace_id == Workplace.id).filter(
                WorkLog.created_at >= week_ago
            ).group_by(Workplace.id).order_by(func.count(WorkLog.id).desc()).limit(10).all()

            if wp_stats:
                wp_names = [w.name[:12] for w in wp_stats]
                wp_counts = [w.cnt for w in wp_stats]
                bars = ax4.bar(wp_names, wp_counts, color=COLORS['info'], width=0.6)
                ax4.tick_params(colors=COLORS['text_secondary'], labelsize=7, rotation=45)
            else:
                ax4.text(0.5, 0.5, 'Нет данных', ha='center', va='center',
                         color=COLORS['text_muted'], fontsize=12, transform=ax4.transAxes)

            ax4.spines['top'].set_visible(False)
            ax4.spines['right'].set_visible(False)
            ax4.spines['bottom'].set_color(COLORS['border'])
            ax4.spines['left'].set_color(COLORS['border'])

            self.fig_workplaces.tight_layout()
            self.canvas_workplaces.draw()

            session.close()
        except Exception as e:
            print(f'General analytics error: {e}')

