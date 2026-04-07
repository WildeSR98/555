"""
Вкладка Проекты — дерево проектов с устройствами и операциями.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QLineEdit, QComboBox, QHeaderView,
    QSplitter, QTableWidget, QTableWidgetItem, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..database import get_session
from ..models import Project, Device, Operation, SerialNumber
from .styles import COLORS, DEVICE_STATUS_COLORS
from .widgets.status_badge import StatusBadge


class ProjectsTab(QWidget):
    """Вкладка Проекты."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Заголовок + фильтры
        header = QHBoxLayout()
        title = QLabel('📋 Проекты')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('🔍 Поиск по коду, имени...')
        self.search_input.setMaximumWidth(250)
        self.search_input.textChanged.connect(self._filter_tree)
        header.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItem('Все статусы', '')
        for code, name in Project.STATUS_DISPLAY.items():
            self.status_filter.addItem(name, code)
        self.status_filter.currentTextChanged.connect(lambda: self.refresh_data())
        self.status_filter.setMaximumWidth(180)
        header.addWidget(self.status_filter)

        refresh_btn = QPushButton('⟳ Обновить')
        refresh_btn.setProperty('class', 'secondary')
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)
        
        create_btn = QPushButton('➕ Создать')
        create_btn.setProperty('class', 'success')
        create_btn.clicked.connect(self._create_project)
        header.addWidget(create_btn)

        layout.addLayout(header)

        # Splitter: дерево | детали
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Дерево проектов
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Элемент', 'Код', 'Статус', 'SN / PN'])
        self.tree.setColumnCount(4)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self.tree)

        # Панель деталей
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(12, 0, 0, 0)

        self.details_title = QLabel('Выберите элемент')
        self.details_title.setStyleSheet('font-size: 18px; font-weight: bold;')
        self.details_title.setWordWrap(True)
        self.details_title.setMinimumWidth(150)
        details_layout.addWidget(self.details_title)

        # Панель статистики проекта (в деталях)
        self.project_stats_widget = QWidget()
        self.project_stats_widget.setVisible(False)
        self.stats_panel = QHBoxLayout(self.project_stats_widget)
        self.stats_panel.setContentsMargins(0, 5, 0, 10)
        self.stats_panel.setSpacing(10)
        
        self.stat_not_started = self._create_stat_card('⚪ Ожид.', '#94a3b8')
        self.stat_in_work = self._create_stat_card('🟡 Работ.', '#3b82f6')
        self.stat_done = self._create_stat_card('🟢 Готов.', '#22c55e')
        
        self.stats_panel.addWidget(self.stat_not_started)
        self.stats_panel.addWidget(self.stat_in_work)
        self.stats_panel.addWidget(self.stat_done)
        
        details_layout.addWidget(self.project_stats_widget)

        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(['Поле', 'Значение'])
        self.details_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.details_table.verticalHeader().setVisible(False)
        self.details_table.setAlternatingRowColors(True)
        self.details_table.setWordWrap(True)
        details_layout.addWidget(self.details_table)

        self.btn_delete_project = QPushButton('🗑 Удалить проект')
        self.btn_delete_project.setProperty('class', 'danger')
        self.btn_delete_project.setVisible(False)
        self.btn_delete_project.clicked.connect(self._delete_project)
        
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        action_layout.addWidget(self.btn_delete_project)
        details_layout.addLayout(action_layout)

        splitter.addWidget(details_widget)
        splitter.setStretchFactor(0, 3) # Дерево занимает 3 части (75%)
        splitter.setStretchFactor(1, 1) # Детали занимают 1 часть (25%)
        # Ограничим также жестко ширину деталей сверху, чтобы длинный текст не ломал сплиттер
        details_widget.setMaximumWidth(450)

        layout.addWidget(splitter)

    def _create_stat_card(self, title: str, color: str) -> QFrame:
        """Создание карточки статистики."""
        card = QFrame()
        card.setFixedHeight(50)
        card.setMinimumWidth(80)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 11px; text-transform: uppercase;")
        layout.addWidget(title_lbl)
        
        # Сохраняем ссылку на ярлык со значением
        value_lbl = QLabel('0')
        value_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(value_lbl)
        
        # Добавляем атрибут к фрейму для легкого доступа
        card.value_label = value_lbl
        return card

    def _create_project(self) -> None:
        """Открытие диалога создания нового проекта."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDialogButtonBox, QMessageBox,
            QGroupBox, QVBoxLayout, QHBoxLayout, QSpinBox, QWidget
        )
        from ..models import User, Device
        from datetime import datetime
        
        dialog = QDialog(self)
        dialog.setWindowTitle('Создать проект')
        dialog.setMinimumWidth(500)
        
        main_layout = QVBoxLayout(dialog)
        
        # Основа
        info_group = QGroupBox('Основная информация')
        form = QFormLayout(info_group)
        
        code_input = QLineEdit()
        name_input = QLineEdit()
        spec_link_input = QLineEdit()
        spec_link_input.setPlaceholderText('https://...')
        spec_code_input = QLineEdit()
        spec_code_input.setPlaceholderText('Код из документации')
        
        manager_combo = QComboBox()
        manager_combo.addItem('— Без менеджера —', None)
        try:
            session = get_session()
            managers = session.query(User).filter(User.is_active == True).all()
            for m in managers:
                manager_combo.addItem(f'{m.full_name} ({m.username})', m.id)
            session.close()
        except Exception:
            pass
            
        form.addRow('Код проекта:', code_input)
        form.addRow('Название (обязательно):', name_input)
        form.addRow('Ссылка на спеку:', spec_link_input)
        form.addRow('Проверочный код:', spec_code_input)
        form.addRow('Менеджер:', manager_combo)
        main_layout.addWidget(info_group)
        
        # Устройства
        dev_group = QGroupBox('Устройства проекта (по партномерам)')
        dev_layout = QVBoxLayout(dev_group)
        
        rows_layout = QVBoxLayout()
        dev_layout.addLayout(rows_layout)
        
        add_btn = QPushButton('➕ Добавить партномер')
        add_btn.setProperty('class', 'secondary')
        dev_layout.addWidget(add_btn)
        main_layout.addWidget(dev_group)
        
        device_rows = []
        
        # Предзагрузим модели один раз для всех строк
        device_models_cache = []
        try:
            temp_session = get_session()
            from ..models import DeviceModel
            device_models_cache = temp_session.query(DeviceModel).order_by(DeviceModel.category, DeviceModel.name).all()
            # Отвяжем их от сессии
            for dm in device_models_cache:
                temp_session.expunge(dm)
            temp_session.close()
        except:
            pass

        def add_device_row():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            pn_input = QLineEdit()
            pn_input.setPlaceholderText('Партномер (PN)')
            
            type_combo = QComboBox()
            # Добавим модели из базы
            from ..models import Device
            for m in device_models_cache:
                cat_display = Device.DEVICE_TYPE_DISPLAY.get(m.category, m.category)
                type_combo.addItem(f"{cat_display} — {m.name}", m.id)
                    
            qty_spin = QSpinBox()
            qty_spin.setMinimum(1)
            qty_spin.setMaximum(1000)
            qty_spin.setSuffix(' шт.')
            qty_spin.setMinimumWidth(80)
            
            remove_btn = QPushButton('❌')
            remove_btn.setMaximumWidth(40)
            remove_btn.clicked.connect(lambda: remove_row(row_widget, pn_input, type_combo, qty_spin))
            
            row_layout.addWidget(pn_input, stretch=1)
            row_layout.addWidget(type_combo)
            row_layout.addWidget(qty_spin)
            row_layout.addWidget(remove_btn)
            
            rows_layout.addWidget(row_widget)
            device_rows.append((pn_input, type_combo, qty_spin))
            
        def remove_row(widget, pn_input, type_combo, qty_spin):
            widget.setParent(None)
            row_tuple = (pn_input, type_combo, qty_spin)
            if row_tuple in device_rows:
                device_rows.remove(row_tuple)
                
        add_btn.clicked.connect(add_device_row)
        add_device_row() # Одна строка по умолчанию
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        main_layout.addWidget(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(self, 'Ошибка', 'Название проекта не может быть пустым')
                return
                
            code = code_input.text().strip()
            manager_id = manager_combo.currentData()
            
            try:
                session = get_session()
                # code = code if code else None (in ORM)
                from ..models import DeviceModel
                new_proj = Project(
                    name=name,
                    code=code if code else None,
                    spec_link=spec_link_input.text().strip() or None,
                    spec_code=spec_code_input.text().strip() or None,
                    status='PLANNING',
                    manager_id=manager_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(new_proj)
                session.flush() # Получаем id проекта
                
                # Словарик для отслеживания текущего индекса при генерации в памяти (в рамках одного коммита)
                current_counters = {}
                
                device_count = 0
                for pn_input, type_combo, qty_spin in device_rows:
                    pn_val = pn_input.text().strip()
                    model_id = type_combo.currentData()
                    qty_val = qty_spin.value()
                    
                    if not pn_val or not model_id:
                        continue
                        
                    dm = session.query(DeviceModel).get(model_id)
                    if not dm:
                        continue
                        
                    prefix = dm.sn_prefix
                    
                    if prefix not in current_counters:
                        # Ищем максимальный индекс в БД для этой модели
                        from sqlalchemy import desc
                        last_sn_record = session.query(SerialNumber).filter(
                            SerialNumber.model_id == dm.id
                        ).order_by(desc(SerialNumber.sn)).first()
                        
                        if last_sn_record:
                            # Вытаскиваем числовую часть
                            num_str = last_sn_record.sn[len(prefix):]
                            try:
                                current_counters[prefix] = int(num_str)
                            except ValueError:
                                current_counters[prefix] = 0
                        else:
                            current_counters[prefix] = 0
                            
                    for i in range(qty_val):
                        device_count += 1
                        
                        # Генерируем новый SN
                        current_counters[prefix] += 1
                        new_sn_str = f"{prefix}{current_counters[prefix]:05d}"
                        
                        new_device = Device(
                            project_id=new_proj.id,
                            name=f"{pn_val} #{i+1}",
                            part_number=pn_val,
                            device_type=dm.category,
                            serial_number=new_sn_str,
                            status='PRE_PRODUCTION',
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        session.add(new_device)
                        session.flush() # Получаем ID для создания SerialNumber
                        
                        new_sn_record = SerialNumber(
                            sn=new_sn_str,
                            model_id=dm.id,
                            is_used=True,
                            device_id=new_device.id,
                            created_at=datetime.now()
                        )
                        session.add(new_sn_record)
                        
                session.commit()
                session.close()
                QMessageBox.information(self, 'Успех', f'Проект создан. Сгенерировано устройств: {device_count}')
                self.refresh_data()
            except Exception as e:
                session.rollback()
                session.close()
                if 'UNIQUE constraint failed' in str(e):
                    QMessageBox.warning(self, 'Ошибка', 'Проект с таким кодом уже существует! Укажите уникальный код.')
                else:
                    QMessageBox.critical(self, 'Ошибка', f'Ошибка при создании проекта:\n{e}')

    def _update_statistics(self, project_id: Optional[int] = None) -> None:
        """Расчет статистики по конкретному проекту."""
        if not project_id:
            self.project_stats_widget.setVisible(False)
            return

        try:
            session = get_session()
            from sqlalchemy import func
            
            # Группировка статусов
            not_started_group = [
                'WAITING_KITTING', 'PRE_PRODUCTION', 'WAITING_ASSEMBLY', 
                'WAITING_PARTS', 'WAITING_SOFTWARE'
            ]
            done_group = ['WAREHOUSE', 'QC_PASSED', 'SHIPPED']
            
            # Статистика только по ОДНОМУ проекту
            stats = session.query(
                Device.status, func.count(Device.id)
            ).filter(Device.project_id == project_id).group_by(Device.status).all()
            
            counts = {'not_started': 0, 'in_work': 0, 'done': 0}
            
            for status, count in stats:
                if status in not_started_group:
                    counts['not_started'] += count
                elif status in done_group:
                    counts['done'] += count
                else:
                    counts['in_work'] += count
            
            # Обновление UI
            self.stat_not_started.value_label.setText(str(counts['not_started']))
            self.stat_in_work.value_label.setText(str(counts['in_work']))
            self.stat_done.value_label.setText(str(counts['done']))
            
            self.project_stats_widget.setVisible(True)
            session.close()
        except Exception as e:
            print(f"Stats error: {e}")

    def refresh_data(self) -> None:
        """Загрузка данных в дерево."""
        self.project_stats_widget.setVisible(False)
        self.tree.clear()
        try:
            session = get_session()

            status_filter = self.status_filter.currentData()
            query = session.query(Project).order_by(Project.created_at.desc())
            if status_filter:
                query = query.filter(Project.status == status_filter)

            projects = query.all()

            for project in projects:
                # Проект
                proj_item = QTreeWidgetItem(self.tree)
                proj_item.setText(0, f'📁 {project.name}')
                proj_item.setText(1, project.code or '')
                proj_item.setText(2, project.status_display)
                proj_item.setData(0, Qt.ItemDataRole.UserRole, ('project', project.id))

                color = Project.STATUS_COLORS.get(project.status, '#6c757d')
                proj_item.setForeground(2, QColor(color))

                # Устройства
                devices = session.query(Device).filter(
                    Device.project_id == project.id
                ).order_by(Device.name).all()

                for device in devices:
                    dev_item = QTreeWidgetItem(proj_item)
                    dev_item.setText(0, f'  💻 {device.name}')
                    dev_item.setText(1, device.code or '')
                    dev_item.setText(2, device.status_display)
                    dev_item.setText(3, f'SN: {device.serial_number}' if device.serial_number else f'PN: {device.part_number}')
                    dev_item.setData(0, Qt.ItemDataRole.UserRole, ('device', device.id))

                    dev_color = Device.STATUS_COLORS.get(device.status, '#6c757d')
                    dev_item.setForeground(2, QColor(dev_color))

                    # Операции
                    operations = session.query(Operation).filter(
                        Operation.device_id == device.id
                    ).order_by(Operation.id).all()

                    for op in operations:
                        op_item = QTreeWidgetItem(dev_item)
                        op_item.setText(0, f'    ⚙ {op.title}')
                        op_item.setText(1, op.code or '')
                        op_item.setText(2, op.status_display)
                        op_item.setData(0, Qt.ItemDataRole.UserRole, ('operation', op.id))

                        op_color = Operation.STATUS_COLORS.get(op.status, '#6c757d')
                        op_item.setForeground(2, QColor(op_color))

            session.close()
        except Exception as e:
            print(f'Projects refresh error: {e}')

    def _filter_tree(self, text: str) -> None:
        """Фильтрация дерева по тексту."""
        text = text.lower().strip()
        matches = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            # Проверяем, совпадает ли сам проект (имя или код)
            parent_match = (
                text in item.text(0).lower() or
                text in item.text(1).lower()
            )
            
            # Проверяем дочерние
            child_match = False
            for j in range(item.childCount()):
                child = item.child(j)
                cm = (
                    text in child.text(0).lower() or
                    text in child.text(1).lower() or
                    text in child.text(3).lower()
                )
                if parent_match:
                    child.setHidden(False)
                else:
                    child.setHidden(bool(text) and not cm)
                
                if cm:
                    child_match = True
                    
            # Скрываем проект, если он не совпал и никто из устройств не совпал
            is_visible = not bool(text) or parent_match or child_match
            item.setHidden(not is_visible)
            
            if is_visible and bool(text):
                item.setExpanded(True)
                # Добавляем в matches, если совпал САМ проект
                if parent_match:
                    matches.append(item)
                    
        # Если проект совпал ровно один, открываем его детали
        if bool(text) and len(matches) == 1:
            self.tree.setCurrentItem(matches[0])
            self._on_item_clicked(matches[0], 0)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Отображение деталей выбранного элемента."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        entity_type, entity_id = data
        self.btn_delete_project.setVisible(entity_type == 'project')
        
        # Обновляем статистику, если выбран проект
        if entity_type == 'project':
            self.current_project_id = entity_id
            self._update_statistics(entity_id)
        else:
            self.project_stats_widget.setVisible(False)

        try:
            session = get_session()

            fields = []
            if entity_type == 'project':
                project = session.query(Project).get(entity_id)
                if project:
                    self.details_title.setText(f'📁 Проект: {project.name}')
                    fields = [
                        ('Код', project.code),
                        ('Название', project.name),
                        ('Статус', project.status_display),
                        ('Спецификация', project.spec_link or '—'),
                        ('Код подтверждения', project.spec_code or '—'),
                        ('Менеджер', project.manager.full_name if project.manager else '—'),
                        ('Дедлайн', str(project.deadline) if project.deadline else '—'),
                        ('Создан', project.created_at.strftime('%d.%m.%Y %H:%M') if project.created_at else '—'),
                        ('Устройств', str(project.devices.count())),
                    ]
            elif entity_type == 'device':
                device = session.query(Device).get(entity_id)
                if device:
                    self.details_title.setText(f'💻 Устройство: {device.name}')
                    fields = [
                        ('Код', device.code or '—'),
                        ('Название', device.name),
                        ('Серийный номер', device.serial_number or '—'),
                        ('Партномер', device.part_number or '—'),
                        ('Тип', device.device_type_display),
                        ('Статус', device.status_display),
                        ('Полуфабрикат', 'Да' if device.is_semifinished else 'Нет'),
                        ('Текущий работник', device.current_worker.full_name if device.current_worker else '—'),
                        ('Расположение', device.location or '—'),
                    ]
            elif entity_type == 'operation':
                from ..models import Operation
                op = session.query(Operation).get(entity_id)
                if op:
                    self.details_title.setText(f'⚙ Операция: {op.title}')
                    fields = [
                        ('Код', op.code or '—'),
                        ('Название', op.title),
                        ('Статус', op.status_display),
                        ('Группа', op.group.name if op.group else '—'),
                        ('Создал', op.created_by.full_name if op.created_by else '—'),
                        ('Создана', op.created_at.strftime('%d.%m.%Y %H:%M') if op.created_at else '—'),
                        ('Завершена', op.completed_at.strftime('%d.%m.%Y %H:%M') if op.completed_at else '—'),
                    ]

            self.details_table.setRowCount(len(fields))
            for i, (key, value) in enumerate(fields):
                self.details_table.setItem(i, 0, QTableWidgetItem(key))
                self.details_table.setItem(i, 1, QTableWidgetItem(str(value)))
                
            self.details_table.resizeRowsToContents()

            session.close()
        except Exception as e:
            print(f'Details error: {e}')

    def _delete_project(self) -> None:
        """Удаление выбранного проекта и всех его данных."""
        if not hasattr(self, 'current_project_id') or not self.current_project_id:
            return
            
        from PyQt6.QtWidgets import QMessageBox
        from ..models import WorkLog, Operation
        
        reply = QMessageBox.question(
            self, 'Подтверждение', 
            'Вы уверены, что хотите удалить этот проект?\n\nВНИМАНИЕ: Это удалит проект, все устройства, операции и записи истории (логи)!',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                session = get_session()
                # Удаляем по каскаду вручную, чтобы избежать блокировок SQLite
                
                # 1. Записи журнала
                session.query(WorkLog).filter(WorkLog.project_id == self.current_project_id).delete()
                
                # 2. Операции устройств
                project = session.query(Project).get(self.current_project_id)
                if project:
                    device_ids = [d.id for d in project.devices]
                    if device_ids:
                        session.query(Operation).filter(Operation.device_id.in_(device_ids)).delete(synchronize_session=False)
                        
                    # 3. Сами устройства
                    session.query(Device).filter(Device.project_id == project.id).delete(synchronize_session=False)
                    
                    # 4. Проект
                    session.delete(project)
                    
                session.commit()
                session.close()
                self.current_project_id = None
                self.btn_delete_project.setVisible(False)
                self.details_title.setText('Выберите элемент')
                self.details_table.setRowCount(0)
                
                QMessageBox.information(self, 'Успех', 'Проект успешно удален.')
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось удалить проект:\n{e}')
