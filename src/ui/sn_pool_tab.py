"""
Вкладка просмотра сгенерированного пула серийных номеров.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QLineEdit, QSplitter, QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from ..database import get_session
from ..models import SerialNumber, Device, DeviceModel


class SNPoolLoadWorker(QObject):
    """Рабочий для фоновой загрузки данных пула SN."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, model_id: int):
        super().__init__()
        self.model_id = model_id

    def run(self):
        try:
            session = get_session()
            query = session.query(SerialNumber).filter(SerialNumber.model_id == self.model_id).order_by(SerialNumber.created_at.desc())
            records = query.all()
            
            data = []
            for rec in records:
                status_str = ''
                status_color = None
                device_str = '—'
                
                if rec.device_id is None and rec.is_used:
                    status_str = '⚙ Сдвиг счетчика (Якорь)'
                    status_color = 'darkYellow'
                else:
                    status_str = '🔴 Использован' if rec.is_used else '🟢 Свободен'
                    
                    if rec.device:
                        proj = rec.device.project
                        device_str = f"💻 {rec.device.name} (📁 {proj.name if proj else 'Без проекта'})"
                
                data.append({
                    'id': rec.id,
                    'sn': rec.sn,
                    'status_str': status_str,
                    'status_color': status_color,
                    'device_str': device_str
                })
            
            session.close()
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class AddModelDialog(QDialog):
    """Окно для добавления новой модели устройства."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Добавить новую модель устройства')
        self.setMinimumWidth(350)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.category_combo = QComboBox()
        for k, v in Device.DEVICE_TYPE_DISPLAY.items():
            if k in Device.SN_PREFIXES:
                self.category_combo.addItem(v, k)
        form.addRow('Категория:', self.category_combo)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('Например: Tioga Type 4')
        form.addRow('Название модели:', self.name_input)

        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText('Например: 60LXTRDC (будет прочитано из категории)')
        form.addRow('Префикс SN:', self.prefix_input)

        self.category_combo.currentIndexChanged.connect(self._auto_fill_prefix)
        self._auto_fill_prefix() # Заполнить для первого элемента

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton('Отмена')
        cancel_btn.setProperty('class', 'secondary')
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton('Сохранить')
        save_btn.clicked.connect(self.accept)

        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _auto_fill_prefix(self) -> None:
        cat_key = self.category_combo.currentData()
        prefix = Device.SN_PREFIXES.get(cat_key, '')
        self.prefix_input.setText(prefix)


from datetime import datetime

class SetCounterDialog(QDialog):
    """Окно для ручной установки счетчика (якоря)."""
    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Установить последний SN')
        self.setMinimumWidth(300)
        self.model_name = model_name
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        info = QLabel(f"Укажите последний номер, выпущенный для <b>{self.model_name}</b>:<br><small>(Следующий будет на 1 больше)</small>")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.count_input = QLineEdit()
        self.count_input.setPlaceholderText('Например: 500')
        form.addRow('Номер:', self.count_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton('Отмена')
        cancel_btn.setProperty('class', 'secondary')
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton('Сохранить якорь')
        save_btn.clicked.connect(self.accept)

        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)


class SNPoolTab(QWidget):
    """Вкладка просмотра всех сгенерированных серийных номеров (разделенных по моделям)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_model_id = None
        self.thread = None
        self.worker = None
        self._setup_ui()
        self.refresh_tree()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Шапка
        header = QHBoxLayout()
        title = QLabel('🔢 Пул серийных номеров')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('🔍 Поиск по SN...')
        self.search_input.setMinimumWidth(200)
        self.search_input.textChanged.connect(self._filter_table)
        header.addWidget(self.search_input)

        add_model_btn = QPushButton('➕ Добавить модель')
        add_model_btn.clicked.connect(self._add_new_model)
        header.addWidget(add_model_btn)

        refresh_btn = QPushButton('⟳ Обновить')
        refresh_btn.setProperty('class', 'secondary')
        refresh_btn.clicked.connect(self.refresh_tree)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Сплиттер для Дерева папок и Таблицы
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Дерево категорий и моделей
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        splitter.addWidget(self.tree)

        # Правая панель таблицы
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        table_header_layout = QHBoxLayout()
        self.table_title = QLabel('Выберите модель устройства...')
        self.table_title.setStyleSheet('font-size: 16px; font-weight: bold; color: #94a3b8;')
        table_header_layout.addWidget(self.table_title)
        table_header_layout.addStretch()
        
        self.set_counter_btn = QPushButton('⚙ Задать счетчик')
        self.set_counter_btn.clicked.connect(self._set_manual_counter)
        self.set_counter_btn.setVisible(False)
        table_header_layout.addWidget(self.set_counter_btn)
        
        right_layout.addLayout(table_header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['ID', 'Серийный номер (SN)', 'Статус', 'Привязанный проект (Устройство)'])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # SN
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Статус
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)          # Проект/Устройство
        
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right_layout.addWidget(self.table)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1) # Дерево (25%)
        splitter.setStretchFactor(1, 3) # Таблица (75%)
        self.tree.setMaximumWidth(350)
        
        layout.addWidget(splitter)

    def _add_new_model(self) -> None:
        dialog = AddModelDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            category_key = dialog.category_combo.currentData()
            name = dialog.name_input.text().strip()
            prefix = dialog.prefix_input.text().strip()

            if not name or not prefix:
                QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены.")
                return

            try:
                session = get_session()
                # Проверим, нет ли уже такой модели
                exists = session.query(DeviceModel).filter_by(category=category_key, name=name).first()
                if exists:
                    QMessageBox.warning(self, "Ошибка", f"Модель '{name}' в категории '{category_key}' уже существует.")
                    session.close()
                    return

                new_model = DeviceModel(
                    category=category_key,
                    name=name,
                    sn_prefix=prefix
                )
                session.add(new_model)
                session.commit()
                session.close()
                self.refresh_tree()
                QMessageBox.information(self, "Успех", f"Модель '{name}' успешно добавлена!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка БД", str(e))

    def refresh_tree(self) -> None:
        self.tree.clear()
        try:
            session = get_session()
            models = session.query(DeviceModel).order_by(DeviceModel.category, DeviceModel.name).all()
            
            categories = {}
            for k, v in Device.DEVICE_TYPE_DISPLAY.items():
                if k in Device.SN_PREFIXES:
                    categories[k] = {"name": v, "models": []}

            for m in models:
                if m.category in categories:
                    categories[m.category]["models"].append(m)

            # Строим дерево
            for cat_key, cat_data in categories.items():
                cat_item = QTreeWidgetItem([cat_data["name"]])
                cat_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "category"})
                # Иконка папки
                cat_item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))

                for mod in cat_data["models"]:
                    mod_item = QTreeWidgetItem([mod.name])
                    mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "model", "id": mod.id, "name": mod.name})
                    cat_item.addChild(mod_item)

                self.tree.addTopLevelItem(cat_item)

            self.tree.expandAll()
            session.close()

            # Если была выбрана модель, обновляем ее таблицу
            if self.current_model_id:
                self._load_table_for_model(self.current_model_id)

        except Exception as e:
            print(f"Ошибка загрузки дерева пула: {e}")

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "model":
            self.current_model_id = data["id"]
            self.table_title.setText(f"Таблица пула: {data['name']}")
            self.set_counter_btn.setVisible(True)
            self._load_table_for_model(self.current_model_id)
        else:
            self.table_title.setText("Выберите модель устройства...")
            self.set_counter_btn.setVisible(False)
            self.table.setRowCount(0)

    def _set_manual_counter(self) -> None:
        if not self.current_model_id:
            return
            
        try:
            session = get_session()
            dm = session.query(DeviceModel).get(self.current_model_id)
            if not dm:
                session.close()
                return
                
            model_name = dm.name
            model_prefix = dm.sn_prefix
            session.close()
        except Exception:
            return
            
        dialog = SetCounterDialog(model_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            num_val = dialog.count_input.text().strip()
            if not num_val.isdigit():
                QMessageBox.warning(self, "Ошибка", "Счетчик должен состоять только из цифр.")
                return
            
            num_int = int(num_val)
            anchor_sn = f"{model_prefix}{num_int:05d}"
            
            try:
                session = get_session()
                # Убедимся, что такого SN еще нет
                exists = session.query(SerialNumber).filter_by(sn=anchor_sn).first()
                if exists:
                    QMessageBox.warning(self, "Ошибка", f"Серийный номер {anchor_sn} уже существует в базе!")
                    session.close()
                    return
                
                # Создаем якорную запись
                anchor_record = SerialNumber(
                    sn=anchor_sn,
                    model_id=self.current_model_id,
                    is_used=True,
                    device_id=None,
                    created_at=datetime.now()
                )
                session.add(anchor_record)
                session.commit()
                session.close()
                
                QMessageBox.information(self, "Успех", f"Якорь {anchor_sn} успешно установлен!\nСледующий выданный номер будет {model_prefix}{num_int+1:05d}.")
                self._load_table_for_model(self.current_model_id)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения: {e}")

    def _load_table_for_model(self, model_id: int) -> None:
        """Переход к асинхронной загрузке таблицы."""
        # Проверка, не запущен ли уже поток
        if hasattr(self, 'thread') and self.thread is not None:
            try:
                if self.thread.isRunning():
                    return
            except RuntimeError:
                # Объект потока был удален на стороне C++, сбрасываем ссылку
                self.thread = None

        self.table.setRowCount(1)
        self.table.setItem(0, 1, QTableWidgetItem("⏳ Загрузка..."))
        
        self.thread = QThread()
        self.worker = SNPoolLoadWorker(model_id)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_table_loaded)
        self.worker.error.connect(self._on_load_error)
        
        # Очистка потока после завершения
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: setattr(self, 'thread', None))

        self.thread.start()

    def _on_table_loaded(self, records_data: list) -> None:
        """Отрисовка полученных данных пула."""
        self.table.setRowCount(len(records_data))

        for row, rec in enumerate(records_data):
            item_id = QTableWidgetItem(str(rec['id']))
            item_sn = QTableWidgetItem(rec['sn'])
            item_status = QTableWidgetItem(rec['status_str'])
            
            if rec['status_color'] == 'darkYellow':
                item_status.setForeground(Qt.GlobalColor.darkYellow)
            
            item_device = QTableWidgetItem(rec['device_str'])

            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_id)
            self.table.setItem(row, 1, item_sn)
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, item_device)

        # Применим текстовый фильтр
        self._filter_table(self.search_input.text())

    def _on_load_error(self, error_msg: str) -> None:
        print(f"Ошибка загрузки таблицы пула: {error_msg}")
        self.table.setRowCount(0)

    def _filter_table(self, text: str) -> None:
        text = text.lower().strip()
        for row in range(self.table.rowCount()):
            sn_item = self.table.item(row, 1)
            if sn_item:
                match = text in sn_item.text().lower()
                self.table.setRowHidden(row, not match)
