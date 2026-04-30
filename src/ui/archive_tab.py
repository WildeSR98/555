"""
Вкладка Архив — завершённые проекты с историей действий.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFrame, QSplitter, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor

from ..database import get_session
from ..models import Project, Device, WorkLog
from .styles import COLORS


class ArchiveLoadWorker(QObject):
    """Фоновая загрузка архивных проектов."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            session = get_session()
            projects = session.query(Project).filter(
                Project.status == 'COMPLETED'
            ).order_by(Project.updated_at.desc()).all()

            data = []
            for p in projects:
                device_count = session.query(Device).filter(Device.project_id == p.id).count()
                data.append({
                    'id': p.id,
                    'name': p.name,
                    'code': p.code or '',
                    'manager': p.manager.full_name if p.manager else '—',
                    'device_count': device_count,
                    'archived_at': p.updated_at.strftime('%d.%m.%Y %H:%M') if p.updated_at else '—',
                })
            session.close()
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class ArchiveLogsWorker(QObject):
    """Фоновая загрузка истории действий по проекту."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, project_id: int):
        super().__init__()
        self.project_id = project_id

    def run(self):
        try:
            session = get_session()
            devices = session.query(Device).filter(
                Device.project_id == self.project_id
            ).order_by(Device.name).all()

            result = []
            for dev in devices:
                logs = session.query(WorkLog).filter(
                    WorkLog.device_id == dev.id
                ).order_by(WorkLog.created_at.asc()).all()

                log_entries = []
                for log in logs:
                    log_entries.append({
                        'created_at': log.created_at.strftime('%d.%m.%Y %H:%M:%S') if log.created_at else '—',
                        'action': log.action_display,
                        'action_raw': log.action,
                        'old_status': Device.STATUS_DISPLAY.get(log.old_status, log.old_status or ''),
                        'new_status': Device.STATUS_DISPLAY.get(log.new_status, log.new_status or ''),
                        'notes': log.notes or '—',
                        'worker': log.worker.full_name if log.worker else '—',
                    })

                result.append({
                    'device_name': dev.name,
                    'serial_number': dev.serial_number or '—',
                    'logs': log_entries,
                })

            session.close()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ArchiveTab(QWidget):
    """Вкладка Архив завершённых проектов."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.all_projects = []
        self.thread = None
        self.worker = None
        self.logs_thread = None
        self.logs_worker = None
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel('📦 Архив проектов')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton('⟳ Обновить')
        refresh_btn.setProperty('class', 'secondary')
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        subtitle = QLabel('Завершённые проекты с историей действий сотрудников')
        subtitle.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 13px;')
        layout.addWidget(subtitle)

        # Поиск
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 4, 8, 4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('🔍 Поиск по названию проекта...')
        self.search_input.setMinimumHeight(32)
        self.search_input.textChanged.connect(self._filter_projects)
        search_layout.addWidget(self.search_input)

        self.count_label = QLabel('')
        self.count_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 13px;')
        search_layout.addWidget(self.count_label)
        layout.addWidget(search_frame)

        # Splitter: таблица проектов | панель истории
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Таблица проектов
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels([
            '', 'Проект', 'Менеджер', 'Устройств', 'Дата архивирования'
        ])
        hdr = self.projects_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # иконка
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Проект
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Менеджер
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Устройств
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Дата

        self.projects_table.setAlternatingRowColors(True)
        self.projects_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.projects_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.cellClicked.connect(self._on_project_clicked)
        top_layout.addWidget(self.projects_table)

        # Статус загрузки
        self.loading_label = QLabel('⏳ Загрузка...')
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; padding: 20px;')
        top_layout.addWidget(self.loading_label)

        self.empty_label = QLabel('📦 Архив пуст. Завершённые проекты появятся здесь.')
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f'color: {COLORS["text_secondary"]}; padding: 40px;')
        self.empty_label.setVisible(False)
        top_layout.addWidget(self.empty_label)

        splitter.addWidget(top_widget)

        # Панель истории
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        log_header = QHBoxLayout()
        self.log_title = QLabel('📋 Нажмите на проект для просмотра истории')
        self.log_title.setStyleSheet(f'font-size: 15px; font-weight: 600; color: {COLORS["text_secondary"]};')
        log_header.addWidget(self.log_title)
        log_header.addStretch()

        self.close_log_btn = QPushButton('✕ Закрыть')
        self.close_log_btn.setProperty('class', 'secondary')
        self.close_log_btn.clicked.connect(self._close_log_panel)
        self.close_log_btn.setVisible(False)
        log_header.addWidget(self.close_log_btn)
        bottom_layout.addLayout(log_header)

        # Таблица истории
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(7)
        self.logs_table.setHorizontalHeaderLabels([
            'Устройство', 'SN', 'Дата/Время', 'Действие', 'Статус', 'Примечание', 'Сотрудник'
        ])
        logs_hdr = self.logs_table.horizontalHeader()
        logs_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Устройство
        logs_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # SN
        logs_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Дата
        logs_hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Действие
        logs_hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Статус
        logs_hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)           # Примечание
        logs_hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Сотрудник

        self.logs_table.setAlternatingRowColors(True)
        self.logs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.logs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.logs_table.verticalHeader().setVisible(False)
        bottom_layout.addWidget(self.logs_table)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([350, 300])
        layout.addWidget(splitter)

    def refresh_data(self) -> None:
        """Запуск фоновой загрузки архивных проектов."""
        if self.thread and self.thread.isRunning():
            return

        self.projects_table.setVisible(False)
        self.empty_label.setVisible(False)
        self.loading_label.setVisible(True)

        self.thread = QThread()
        self.worker = ArchiveLoadWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_data_loaded)
        self.worker.error.connect(self._on_load_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: setattr(self, 'thread', None))

        self.thread.start()

    def _on_data_loaded(self, data: list) -> None:
        self.all_projects = data
        self.loading_label.setVisible(False)

        if not data:
            self.empty_label.setVisible(True)
            self.projects_table.setVisible(False)
            self.count_label.setText('Проектов: 0')
            return

        self.projects_table.setVisible(True)
        self._render_table(data)

    def _render_table(self, projects: list) -> None:
        self.projects_table.setRowCount(len(projects))
        self.count_label.setText(f'Найдено: {len(projects)}')

        for i, p in enumerate(projects):
            # Иконка
            icon_item = QTableWidgetItem('▶')
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_item.setForeground(QColor(COLORS['accent']))
            icon_item.setData(Qt.ItemDataRole.UserRole, p['id'])
            self.projects_table.setItem(i, 0, icon_item)

            # Название + код
            name_text = p['name']
            if p['code']:
                name_text += f"  [{p['code']}]"
            name_item = QTableWidgetItem(name_text)
            name_item.setFont(self.projects_table.font())
            self.projects_table.setItem(i, 1, name_item)

            self.projects_table.setItem(i, 2, QTableWidgetItem(p['manager']))

            count_item = QTableWidgetItem(f"{p['device_count']} шт.")
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.projects_table.setItem(i, 3, count_item)

            date_item = QTableWidgetItem(p['archived_at'])
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.projects_table.setItem(i, 4, date_item)

    def _filter_projects(self, text: str) -> None:
        q = text.lower().strip()
        if not q:
            filtered = self.all_projects
        else:
            filtered = [
                p for p in self.all_projects
                if q in p['name'].lower() or q in p['code'].lower()
            ]
        self._render_table(filtered)

    def _on_project_clicked(self, row: int, col: int) -> None:
        id_item = self.projects_table.item(row, 0)
        if not id_item:
            return
        project_id = id_item.data(Qt.ItemDataRole.UserRole)
        name_item = self.projects_table.item(row, 1)
        project_name = name_item.text() if name_item else '?'
        self._load_logs(project_id, project_name)

    def _load_logs(self, project_id: int, project_name: str) -> None:
        self.log_title.setText(f'📋 История: {project_name} — загрузка...')
        self.close_log_btn.setVisible(True)
        self.logs_table.setRowCount(0)

        if self.logs_thread and self.logs_thread.isRunning():
            return

        self.logs_thread = QThread()
        self.logs_worker = ArchiveLogsWorker(project_id)
        self.logs_worker.moveToThread(self.logs_thread)

        self.logs_thread.started.connect(self.logs_worker.run)
        self.logs_worker.finished.connect(lambda data: self._on_logs_loaded(data, project_name))
        self.logs_worker.error.connect(self._on_logs_error)

        self.logs_worker.finished.connect(self.logs_thread.quit)
        self.logs_worker.finished.connect(self.logs_worker.deleteLater)
        self.logs_thread.finished.connect(self.logs_thread.deleteLater)
        self.logs_thread.finished.connect(lambda: setattr(self, 'logs_thread', None))

        self.logs_thread.start()

    def _on_logs_loaded(self, devices: list, project_name: str) -> None:
        self.log_title.setText(f'📋 История: {project_name}')

        # Собираем все строки
        all_rows = []
        for dev in devices:
            for log in dev['logs']:
                all_rows.append({
                    'device_name': dev['device_name'],
                    'serial_number': dev['serial_number'],
                    **log,
                })

        if not all_rows:
            self.logs_table.setRowCount(1)
            empty_item = QTableWidgetItem('История пуста')
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.logs_table.setItem(0, 0, empty_item)
            self.logs_table.setSpan(0, 0, 1, 7)
            return

        action_colors = {
            'COMPLETED': COLORS['success'],
            'DEFECT': COLORS['error'],
            'SCAN_IN': COLORS['info'],
            'MAKE_SEMIFINISHED': COLORS['accent'],
        }

        self.logs_table.setRowCount(len(all_rows))
        for i, row in enumerate(all_rows):
            self.logs_table.setItem(i, 0, QTableWidgetItem(row['device_name']))
            self.logs_table.setItem(i, 1, QTableWidgetItem(row['serial_number']))
            self.logs_table.setItem(i, 2, QTableWidgetItem(row['created_at']))

            action_item = QTableWidgetItem(row['action'])
            color = action_colors.get(row['action_raw'], COLORS['accent'])
            action_item.setForeground(QColor(color))
            self.logs_table.setItem(i, 3, action_item)

            status_text = f"{row['old_status']} → {row['new_status']}" if row['old_status'] else row['new_status']
            self.logs_table.setItem(i, 4, QTableWidgetItem(status_text))

            notes_text = row['notes'] if row['notes'] != '—' else ''
            self.logs_table.setItem(i, 5, QTableWidgetItem(notes_text))
            self.logs_table.setItem(i, 6, QTableWidgetItem(row['worker']))

    def _on_logs_error(self, err: str) -> None:
        self.log_title.setText(f'❌ Ошибка загрузки истории: {err[:60]}')

    def _close_log_panel(self) -> None:
        self.logs_table.setRowCount(0)
        self.log_title.setText('📋 Нажмите на проект для просмотра истории')
        self.close_log_btn.setVisible(False)

    def _on_load_error(self, err: str) -> None:
        self.loading_label.setText(f'❌ Ошибка загрузки: {err[:80]}')
