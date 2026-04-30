"""
Вкладка Маршрутные листы — настройка производственных маршрутов.
Суб-вкладки: Маршруты (глобальные) | Проекты (индивидуальные).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame,
    QLineEdit, QDialog, QFormLayout, QComboBox, QMessageBox,
    QCheckBox, QSpinBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont

from ..database import get_session
from ..models import RouteConfig, RouteConfigStage, Project, ProjectRouteStage, User
from ..models import ROUTE_PIPELINE_STAGES
from .styles import COLORS

# Роли с правом редактирования
CAN_EDIT_ROLES = {User.ROLE_ADMIN, User.ROLE_ROOT, User.ROLE_MANAGER}


class RouteConfigsTab(QWidget):
    """Вкладка Маршрутные листы."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.can_edit = user.role in CAN_EDIT_ROLES or user.is_superuser
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel('📋 Маршрутные листы')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        subtitle = QLabel('Конфигурации производственного конвейера по типам устройств')
        subtitle.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 13px;')
        layout.addWidget(subtitle)

        # Суб-вкладки
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{
                padding: 8px 20px; font-size: 13px; font-weight: 600;
            }}
            QTabBar::tab:selected {{
                color: {COLORS['accent']};
                border-bottom: 2px solid {COLORS['accent']};
            }}
        """)

        # Вкладка 1: Маршруты
        self.routes_tab = RoutesSubTab(self.user, self.can_edit)
        self.tabs.addTab(self.routes_tab, '📋 Маршруты')

        # Вкладка 2: Проекты
        self.projects_tab = ProjectsSubTab(self.user, self.can_edit)
        self.tabs.addTab(self.projects_tab, '📁 Проекты')

        layout.addWidget(self.tabs)


class RoutesSubTab(QWidget):
    """Суб-вкладка: глобальные маршруты."""

    def __init__(self, user, can_edit: bool, parent=None):
        super().__init__(parent)
        self.user = user
        self.can_edit = can_edit
        self.current_config = None
        self.all_configs = []
        self._setup_ui()
        self._load_configs()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        if self.can_edit:
            btn_bar = QHBoxLayout()
            btn_bar.addStretch()
            self.create_btn = QPushButton('➕ Создать маршрут')
            self.create_btn.clicked.connect(self._create_route)
            btn_bar.addWidget(self.create_btn)
            layout.addLayout(btn_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая панель — список
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel('Маршруты')
        list_label.setStyleSheet(f'font-size: 11px; color: {COLORS["text_secondary"]}; text-transform: uppercase;')
        left_layout.addWidget(list_label)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(220)
        self.list_widget.currentRowChanged.connect(self._on_route_selected)
        left_layout.addWidget(self.list_widget)

        splitter.addWidget(left)

        # Правая панель — редактор (заполняется позже)
        self.editor_frame = QFrame()
        self.editor_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        self.editor_layout = QVBoxLayout(self.editor_frame)
        self._show_placeholder()
        splitter.addWidget(self.editor_frame)
        splitter.setSizes([240, 700])

        layout.addWidget(splitter)

    def _show_placeholder(self) -> None:
        while self.editor_layout.count():
            self.editor_layout.takeAt(0).widget().deleteLater() if self.editor_layout.itemAt(0).widget() else None
            self.editor_layout.takeAt(0)
        lbl = QLabel('🗂️\n\nВыберите маршрут из списка или создайте новый')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f'color: {COLORS["text_secondary"]}; font-size: 13px;')
        self.editor_layout.addWidget(lbl)

    def _load_configs(self) -> None:
        try:
            session = get_session()
            configs = session.query(RouteConfig).order_by(RouteConfig.is_default.desc(), RouteConfig.name).all()
            self.all_configs = [
                {'id': c.id, 'name': c.name, 'is_default': c.is_default,
                 'device_type': c.device_type or '', 'description': c.description or ''}
                for c in configs
            ]
            session.close()
        except Exception as e:
            self.all_configs = []
            print(f'RouteConfigs load error: {e}')

        self.list_widget.clear()
        for cfg in self.all_configs:
            prefix = '⭐ ' if cfg['is_default'] else '   '
            item = QListWidgetItem(f"{prefix}{cfg['name']}")
            item.setData(Qt.ItemDataRole.UserRole, cfg['id'])
            if cfg['is_default']:
                item.setForeground(QColor('#7c3aed'))
            self.list_widget.addItem(item)

    def _on_route_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.all_configs):
            return
        config_id = self.all_configs[row]['id']
        self._load_and_show_editor(config_id)

    def _load_and_show_editor(self, config_id: int) -> None:
        try:
            session = get_session()
            cfg = session.query(RouteConfig).get(config_id)
            if not cfg:
                session.close()
                return
            self.current_config = {
                'id': cfg.id,
                'name': cfg.name,
                'description': cfg.description or '',
                'device_type': cfg.device_type or '',
                'is_default': cfg.is_default,
                'stages': [
                    {'key': s.stage_key, 'order': s.order_index,
                     'enabled': s.is_enabled, 'label': s.label or '',
                     'timer': s.timer_seconds or 300}
                    for s in cfg.stages
                ]
            }
            session.close()
            self._render_editor()
        except Exception as e:
            print(f'Route editor load error: {e}')

    def _create_route(self) -> None:
        dlg = CreateRouteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                from datetime import datetime
                session = get_session()
                # Берём этапы из дефолтного маршрута
                default_cfg = session.query(RouteConfig).filter(RouteConfig.is_default == True).first()
                new_cfg = RouteConfig(
                    name=data['name'],
                    description=data['description'],
                    device_type=data['device_type'] or None,
                    is_default=False,
                    created_at=datetime.now(),
                )
                session.add(new_cfg)
                session.flush()
                if default_cfg:
                    for s in default_cfg.stages:
                        new_stage = RouteConfigStage(
                            route_config_id=new_cfg.id,
                            stage_key=s.stage_key,
                            order_index=s.order_index,
                            is_enabled=s.is_enabled,
                            label=s.label,
                            timer_seconds=s.timer_seconds,
                        )
                        session.add(new_stage)
                else:
                    for key, label, order in ROUTE_PIPELINE_STAGES:
                        session.add(RouteConfigStage(
                            route_config_id=new_cfg.id,
                            stage_key=key, order_index=order, is_enabled=True
                        ))
                session.commit()
                new_id = new_cfg.id
                session.close()
                self._load_configs()
                # Выбрать созданный
                for i, c in enumerate(self.all_configs):
                    if c['id'] == new_id:
                        self.list_widget.setCurrentRow(i)
                        break
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', str(e))

    # ── 2c: редактор этапов ──────────────────────────────────────
    def _render_editor(self) -> None:
        cfg = self.current_config
        if not cfg:
            return

        # Очистить frame
        for i in reversed(range(self.editor_layout.count())):
            item = self.editor_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        self.editor_layout.update()

        # Заголовок редактора
        hdr = QHBoxLayout()
        name_lbl = QLabel(cfg['name'])
        name_lbl.setStyleSheet('font-size: 18px; font-weight: bold;')
        hdr.addWidget(name_lbl)
        hdr.addStretch()
        if self.can_edit and not cfg['is_default']:
            del_btn = QPushButton('🗑 Удалить')
            del_btn.setStyleSheet(f'background:{COLORS["error"]}; color:white; border:none; border-radius:4px; padding:6px 14px;')
            del_btn.clicked.connect(self._delete_current)
            hdr.addWidget(del_btn)
        self.editor_layout.addLayout(hdr)

        if cfg['device_type']:
            dt_lbl = QLabel(f'📦 {cfg["device_type"]}')
            dt_lbl.setStyleSheet(f'color:{COLORS["accent"]}; font-size:12px;')
            self.editor_layout.addWidget(dt_lbl)

        if cfg['is_default']:
            ro_lbl = QLabel('⚠️ Дефолтный маршрут — только для просмотра')
            ro_lbl.setStyleSheet('color:#7c3aed; font-size:12px;')
            self.editor_layout.addWidget(ro_lbl)

        # Таблица этапов
        self.stage_table = QTableWidget()
        self.stage_table.setColumnCount(4 if (self.can_edit and not cfg['is_default']) else 3)
        headers = ['#', 'Этап', 'Таймер (сек)']
        if self.can_edit and not cfg['is_default']:
            headers.append('Активен')
        self.stage_table.setHorizontalHeaderLabels(headers)
        self.stage_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.stage_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.stage_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        if self.can_edit and not cfg['is_default']:
            self.stage_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.stage_table.verticalHeader().setVisible(False)
        self.stage_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        stages = cfg['stages']
        self.stage_table.setRowCount(len(stages))
        self._stage_checkboxes = []
        self._stage_spinboxes = []

        for row, s in enumerate(stages):
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stage_table.setItem(row, 0, num_item)

            # Метка этапа
            label = s['label'] if s['label'] else dict(ROUTE_PIPELINE_STAGES).get(s['key'], {})
            display = s['label'] or next((lbl for k, lbl, _ in ROUTE_PIPELINE_STAGES if k == s['key']), s['key'])
            if not s['enabled']:
                display += ' (выкл.)'
            lbl_item = QTableWidgetItem(display)
            if not s['enabled']:
                lbl_item.setForeground(QColor(COLORS['text_secondary']))
            self.stage_table.setItem(row, 1, lbl_item)

            # Спинбокс таймера
            spin = QSpinBox()
            spin.setRange(1, 86400)
            spin.setValue(s['timer'])
            spin.setSuffix(' с')
            spin.setEnabled(self.can_edit and not cfg['is_default'])
            self.stage_table.setCellWidget(row, 2, spin)
            self._stage_spinboxes.append(spin)

            # Чекбокс активности
            if self.can_edit and not cfg['is_default']:
                cb = QCheckBox()
                cb.setChecked(s['enabled'])
                cb_widget = QWidget()
                cb_layout = QHBoxLayout(cb_widget)
                cb_layout.addWidget(cb)
                cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                self.stage_table.setCellWidget(row, 3, cb_widget)
                self._stage_checkboxes.append(cb)
            else:
                self._stage_checkboxes.append(None)

        self.editor_layout.addWidget(self.stage_table)

        # Кнопки сохранения
        if self.can_edit and not cfg['is_default']:
            btn_bar = QHBoxLayout()
            save_btn = QPushButton('💾 Сохранить')
            save_btn.setStyleSheet(f'background:{COLORS["accent"]}; color:white; border:none; border-radius:4px; padding:8px 20px; font-weight:bold;')
            save_btn.clicked.connect(self._save_current)
            btn_bar.addWidget(save_btn)
            btn_bar.addStretch()
            self.editor_layout.addLayout(btn_bar)

    # ── 2d: сохранение и удаление ────────────────────────────────
    def _save_current(self) -> None:
        if not self.current_config:
            return
        try:
            session = get_session()
            cfg = session.query(RouteConfig).get(self.current_config['id'])
            for row, stage_data in enumerate(self.current_config['stages']):
                db_stage = session.query(RouteConfigStage).filter(
                    RouteConfigStage.route_config_id == cfg.id,
                    RouteConfigStage.stage_key == stage_data['key']
                ).first()
                if db_stage:
                    db_stage.timer_seconds = self._stage_spinboxes[row].value()
                    cb = self._stage_checkboxes[row]
                    if cb is not None:
                        db_stage.is_enabled = cb.isChecked()
            session.commit()
            session.close()
            QMessageBox.information(self, 'Сохранено', f'Маршрут «{self.current_config["name"]}» сохранён.')
            self._load_and_show_editor(self.current_config['id'])
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _delete_current(self) -> None:
        if not self.current_config or self.current_config['is_default']:
            return
        if QMessageBox.question(self, 'Удаление', f'Удалить маршрут «{self.current_config["name"]}»?',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            session = get_session()
            cfg = session.query(RouteConfig).get(self.current_config['id'])
            if cfg:
                session.delete(cfg)
                session.commit()
            session.close()
            self.current_config = None
            self._load_configs()
            self._show_placeholder()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))


# ── 2e+2f: Суб-вкладка Проекты ──────────────────────────────────────────────

class ProjectsSubTab(QWidget):
    """Суб-вкладка: маршруты по проектам."""

    def __init__(self, user, can_edit: bool, parent=None):
        super().__init__(parent)
        self.user = user
        self.can_edit = can_edit
        self.current_project_id = None
        self.current_device_type = None
        self._setup_ui()
        self._load_projects()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая панель — дерево проектов
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.search = QLineEdit()
        self.search.setPlaceholderText('🔍 Поиск проекта...')
        self.search.textChanged.connect(self._filter)
        left_layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(260)
        self.list_widget.currentItemChanged.connect(self._on_item_selected)
        left_layout.addWidget(self.list_widget)

        splitter.addWidget(left)

        # Правая панель — редактор
        self.editor_frame = QFrame()
        self.editor_frame.setStyleSheet(f'background:{COLORS["bg_surface"]}; border:1px solid {COLORS["border"]}; border-radius:8px;')
        self.editor_layout = QVBoxLayout(self.editor_frame)
        lbl = QLabel('📁\n\nВыберите проект и тип устройства')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f'color:{COLORS["text_secondary"]}; font-size:13px;')
        self.editor_layout.addWidget(lbl)
        splitter.addWidget(self.editor_frame)
        splitter.setSizes([280, 660])
        layout.addWidget(splitter)

    def _load_projects(self) -> None:
        self.list_widget.clear()
        self._items_meta = []
        try:
            session = get_session()
            from sqlalchemy import func
            from ..models import Device
            projects = session.query(Project).filter(
                Project.status.in_(['ACTIVE', 'PLANNING', 'ON_HOLD'])
            ).order_by(Project.name).all()

            for p in projects:
                dtypes = [r[0] for r in session.query(Device.device_type).filter(
                    Device.project_id == p.id
                ).distinct().all()]
                if not dtypes:
                    continue
                # Заголовок проекта
                hdr_item = QListWidgetItem(f'📁 {p.name}')
                hdr_item.setFlags(hdr_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                hdr_item.setForeground(QColor(COLORS['text_primary']))
                f = hdr_item.font()
                f.setBold(True)
                hdr_item.setFont(f)
                hdr_item.setData(Qt.ItemDataRole.UserRole, None)
                self.list_widget.addItem(hdr_item)
                self._items_meta.append(None)

                for dt in sorted(dtypes):
                    child_item = QListWidgetItem(f'    📦 {dt}')
                    child_item.setData(Qt.ItemDataRole.UserRole, (p.id, dt, p.name))
                    self.list_widget.addItem(child_item)
                    self._items_meta.append((p.id, dt, p.name))

            session.close()
        except Exception as e:
            print(f'ProjectsSubTab load error: {e}')

    def _filter(self, text: str) -> None:
        q = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(bool(q) and q not in item.text().lower())

    def _on_item_selected(self, item) -> None:
        if not item:
            return
        meta = item.data(Qt.ItemDataRole.UserRole)
        if not meta:
            return
        project_id, device_type, project_name = meta
        self.current_project_id = project_id
        self.current_device_type = device_type
        self._load_editor(project_id, device_type, project_name)

    def _load_editor(self, project_id: int, device_type: str, project_name: str) -> None:
        # Очистить редактор
        for i in reversed(range(self.editor_layout.count())):
            w = self.editor_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        try:
            session = get_session()
            stages_db = session.query(ProjectRouteStage).filter(
                ProjectRouteStage.project_id == project_id,
                ProjectRouteStage.device_type == device_type,
            ).order_by(ProjectRouteStage.order_index).all()

            is_override = bool(stages_db)
            if not is_override:
                # fallback: глобальный маршрут для этого device_type
                global_cfg = session.query(RouteConfig).filter(
                    RouteConfig.device_type == device_type
                ).first()
                if not global_cfg:
                    global_cfg = session.query(RouteConfig).filter(RouteConfig.is_default == True).first()
                stages_data = [
                    {'key': s.stage_key, 'enabled': s.is_enabled, 'label': s.label or '', 'timer': s.timer_seconds or 300}
                    for s in (global_cfg.stages if global_cfg else [])
                ]
            else:
                stages_data = [
                    {'key': s.stage_key, 'enabled': s.is_enabled, 'label': s.label or '', 'timer': s.timer_seconds or 300}
                    for s in stages_db
                ]
            session.close()

            self._pr_stages = stages_data

            # Заголовок
            hdr_lbl = QLabel(f'{project_name}  →  📦 {device_type}')
            hdr_lbl.setStyleSheet('font-size:16px; font-weight:bold;')
            self.editor_layout.addWidget(hdr_lbl)

            status_lbl = QLabel('✅ Индивидуальный маршрут' if is_override else '⚫ Используется глобальный маршрут')
            status_lbl.setStyleSheet(f'color:{"#22c55e" if is_override else COLORS["text_secondary"]}; font-size:12px;')
            self.editor_layout.addWidget(status_lbl)

            # Таблица
            self._pr_table = QTableWidget()
            cols = 4 if self.can_edit else 3
            self._pr_table.setColumnCount(cols)
            hdrs = ['#', 'Этап', 'Таймер (сек)']
            if self.can_edit:
                hdrs.append('Активен')
            self._pr_table.setHorizontalHeaderLabels(hdrs)
            self._pr_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self._pr_table.verticalHeader().setVisible(False)
            self._pr_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._pr_table.setRowCount(len(stages_data))
            self._pr_spins = []
            self._pr_checks = []

            for row, s in enumerate(stages_data):
                self._pr_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                display = s['label'] or next((lbl for k, lbl, _ in ROUTE_PIPELINE_STAGES if k == s['key']), s['key'])
                self._pr_table.setItem(row, 1, QTableWidgetItem(display))
                spin = QSpinBox()
                spin.setRange(1, 86400)
                spin.setValue(s['timer'])
                spin.setSuffix(' с')
                spin.setEnabled(self.can_edit)
                self._pr_table.setCellWidget(row, 2, spin)
                self._pr_spins.append(spin)
                if self.can_edit:
                    cb = QCheckBox()
                    cb.setChecked(s['enabled'])
                    cw = QWidget()
                    cl = QHBoxLayout(cw)
                    cl.addWidget(cb)
                    cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.setContentsMargins(0, 0, 0, 0)
                    self._pr_table.setCellWidget(row, 3, cw)
                    self._pr_checks.append(cb)
                else:
                    self._pr_checks.append(None)

            self.editor_layout.addWidget(self._pr_table)

            if self.can_edit:
                btn_bar = QHBoxLayout()
                save_btn = QPushButton('💾 Сохранить для проекта')
                save_btn.setStyleSheet(f'background:{COLORS["accent"]}; color:white; border:none; border-radius:4px; padding:8px 20px; font-weight:bold;')
                save_btn.clicked.connect(self._save_pr)
                btn_bar.addWidget(save_btn)
                if is_override:
                    reset_btn = QPushButton('↺ Сбросить до глобального')
                    reset_btn.setStyleSheet(f'background:rgba(239,68,68,.1); color:#ef4444; border:1px solid rgba(239,68,68,.3); border-radius:4px; padding:8px 20px;')
                    reset_btn.clicked.connect(self._reset_pr)
                    btn_bar.addWidget(reset_btn)
                btn_bar.addStretch()
                self.editor_layout.addLayout(btn_bar)

        except Exception as e:
            err_lbl = QLabel(f'❌ Ошибка: {e}')
            self.editor_layout.addWidget(err_lbl)

    def _save_pr(self) -> None:
        if not self.current_project_id:
            return
        try:
            session = get_session()
            session.query(ProjectRouteStage).filter(
                ProjectRouteStage.project_id == self.current_project_id,
                ProjectRouteStage.device_type == self.current_device_type,
            ).delete()
            for row, s in enumerate(self._pr_stages):
                cb = self._pr_checks[row]
                session.add(ProjectRouteStage(
                    project_id=self.current_project_id,
                    device_type=self.current_device_type,
                    stage_key=s['key'],
                    order_index=row + 1,
                    is_enabled=cb.isChecked() if cb else s['enabled'],
                    label=s['label'] or None,
                    timer_seconds=self._pr_spins[row].value(),
                ))
            session.commit()
            session.close()
            QMessageBox.information(self, 'Сохранено', 'Маршрут проекта сохранён.')
            # Перезагрузить
            item = self.list_widget.currentItem()
            if item:
                meta = item.data(Qt.ItemDataRole.UserRole)
                if meta:
                    self._load_editor(*meta)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _reset_pr(self) -> None:
        if not self.current_project_id:
            return
        if QMessageBox.question(self, 'Сброс', 'Сбросить индивидуальный маршрут до глобального?',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            session = get_session()
            session.query(ProjectRouteStage).filter(
                ProjectRouteStage.project_id == self.current_project_id,
                ProjectRouteStage.device_type == self.current_device_type,
            ).delete()
            session.commit()
            session.close()
            item = self.list_widget.currentItem()
            if item:
                meta = item.data(Qt.ItemDataRole.UserRole)
                if meta:
                    self._load_editor(*meta)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))


# ── Диалог создания маршрута ─────────────────────────────────────────────────

DEVICE_TYPES = ['', 'TIOGA', 'JBOH', 'JBOX', 'SERVAL', 'OCTOPUS', 'PC', 'MONITOR', 'RACK']

class CreateRouteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Новый маршрутный лист')
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Напр. «Tioga — без ОТК 2»')
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText('Краткое описание')
        self.dt_combo = QComboBox()
        for dt in DEVICE_TYPES:
            self.dt_combo.addItem(dt if dt else '— Без привязки —', dt)

        form.addRow('Название *:', self.name_edit)
        form.addRow('Описание:', self.desc_edit)
        form.addRow('Тип устройства:', self.dt_combo)
        layout.addLayout(form)

        hint = QLabel('💡 Маршрут создаётся на основе стандартного (все этапы включены).')
        hint.setStyleSheet('font-size:11px; color:#94a3b8;')
        layout.addWidget(hint)

        btns = QHBoxLayout()
        cancel = QPushButton('Отмена')
        cancel.clicked.connect(self.reject)
        ok = QPushButton('✅ Создать')
        ok.setStyleSheet(f'background:{COLORS["accent"]}; color:white; border:none; border-radius:4px; padding:8px 16px; font-weight:bold;')
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, 'Ошибка', 'Введите название маршрута')
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            'name': self.name_edit.text().strip(),
            'description': self.desc_edit.text().strip(),
            'device_type': self.dt_combo.currentData(),
        }
