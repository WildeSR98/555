"""
Вкладка Сканирование — рабочий процесс на производственной линии.
Шаг 1: Выбор рабочего места + QR работника
Шаг 2: Сканирование SN устройства (Пакетное)
Шаг 3: Действие (Готово / Брак / Оставить / Полуфабрикат)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QStackedWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QListWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from datetime import datetime

from ..database import get_session
from ..models import (
    Workplace, WorkSession, WorkLog, Device, User
)
from .styles import COLORS


class ScanTab(QWidget):
    """Вкладка Сканирование — производственный процесс."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.current_workplace = None
        self.current_worker = None
        self.current_session = None
        self.current_devices = []
        self.scanned_sns = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок
        title = QLabel('📱 Сканирование')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        layout.addWidget(title)

        # Стек шагов
        self.stack = QStackedWidget()

        # Шаг 1: Выбор рабочего места + работник
        self.stack.addWidget(self._create_step1())
        # Шаг 2: Сканирование SN
        self.stack.addWidget(self._create_step2())
        # Шаг 3: Действие с устройством
        self.stack.addWidget(self._create_step3())

        layout.addWidget(self.stack)

    def _create_step1(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        step_label = QLabel('Шаг 1 из 3')
        step_label.setStyleSheet(f'font-size: 12px; color: {COLORS["accent"]}; font-weight: 600;')
        layout.addWidget(step_label)

        heading = QLabel('Выберите рабочее место и отсканируйте QR работника')
        heading.setStyleSheet('font-size: 16px; font-weight: 600;')
        layout.addWidget(heading)

        wp_group = QGroupBox('Рабочее место')
        wp_layout = QVBoxLayout(wp_group)

        self.workplace_combo = QComboBox()
        self.workplace_combo.setMinimumHeight(36)
        self._load_workplaces()
        wp_layout.addWidget(self.workplace_combo)
        layout.addWidget(wp_group)

        worker_group = QGroupBox('QR-код работника')
        worker_layout = QVBoxLayout(worker_group)

        self.worker_input = QLineEdit()
        self.worker_input.setPlaceholderText('Сканируйте QR-код или введите имя пользователя...')
        self.worker_input.setMinimumHeight(40)
        self.worker_input.setFont(QFont('Segoe UI', 14))
        self.worker_input.returnPressed.connect(self._on_worker_scanned)
        worker_layout.addWidget(self.worker_input)

        self.worker_status = QLabel('')
        worker_layout.addWidget(self.worker_status)
        layout.addWidget(worker_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        next_btn = QPushButton('Далее →')
        next_btn.setMinimumWidth(150)
        next_btn.setMinimumHeight(40)
        next_btn.clicked.connect(self._on_worker_scanned)
        btn_layout.addWidget(next_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    def _create_step2(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        step_label = QLabel('Шаг 2 из 3')
        step_label.setStyleSheet(f'font-size: 12px; color: {COLORS["accent"]}; font-weight: 600;')
        layout.addWidget(step_label)

        self.step2_info = QLabel('')
        self.step2_info.setStyleSheet('font-size: 14px;')
        layout.addWidget(self.step2_info)

        sn_group = QGroupBox('Серийный номер устройства (Пакетный сбор)')
        sn_layout = QVBoxLayout(sn_group)

        self.sn_input = QLineEdit()
        self.sn_input.setPlaceholderText('Сканируйте SN (нажмите Enter)...')
        self.sn_input.setMinimumHeight(44)
        self.sn_input.setFont(QFont('Segoe UI', 16))
        self.sn_input.returnPressed.connect(self._add_to_batch)
        sn_layout.addWidget(self.sn_input)

        self.batch_list = QListWidget()
        self.batch_list.setMaximumHeight(150)
        sn_layout.addWidget(self.batch_list)

        self.sn_status = QLabel('')
        sn_layout.addWidget(self.sn_status)
        layout.addWidget(sn_group)

        btn_layout = QHBoxLayout()
        back_btn = QPushButton('← Назад')
        back_btn.setProperty('class', 'secondary')
        back_btn.clicked.connect(self._end_session)
        btn_layout.addWidget(back_btn)

        clear_btn = QPushButton('Очистить список')
        clear_btn.setProperty('class', 'secondary')
        clear_btn.clicked.connect(self._clear_batch)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()

        process_btn = QPushButton('Завершить партию →')
        process_btn.setMinimumWidth(180)
        process_btn.setMinimumHeight(40)
        process_btn.clicked.connect(self._process_batch)
        btn_layout.addWidget(process_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    def _create_step3(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        step_label = QLabel('Шаг 3 из 3')
        step_label.setStyleSheet(f'font-size: 12px; color: {COLORS["accent"]}; font-weight: 600;')
        layout.addWidget(step_label)

        self.step3_info = QLabel('')
        self.step3_info.setStyleSheet('font-size: 14px;')
        self.step3_info.setWordWrap(True)
        layout.addWidget(self.step3_info)

        self.device_info_frame = QFrame()
        self.device_info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        device_info_layout = QVBoxLayout(self.device_info_frame)
        self.device_detail_label = QLabel('')
        self.device_detail_label.setWordWrap(True)
        device_info_layout.addWidget(self.device_detail_label)
        layout.addWidget(self.device_info_frame)

        actions_group = QGroupBox('Выберите действие')
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setSpacing(12)

        self.btn_complete = QPushButton('✅ Готово')
        self.btn_complete.setProperty('class', 'success')
        self.btn_complete.setMinimumHeight(50)
        self.btn_complete.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        self.btn_complete.clicked.connect(lambda: self._do_action('complete'))
        actions_layout.addWidget(self.btn_complete)

        self.btn_in_progress = QPushButton('▶ В работе')
        self.btn_in_progress.setProperty('class', 'primary')
        self.btn_in_progress.setMinimumHeight(50)
        self.btn_in_progress.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        self.btn_in_progress.setStyleSheet('background-color: #3b82f6; color: white;')
        self.btn_in_progress.clicked.connect(lambda: self._do_action('in_progress'))
        actions_layout.addWidget(self.btn_in_progress)

        self.btn_defect = QPushButton('⚠ Брак')
        self.btn_defect.setProperty('class', 'danger')
        self.btn_defect.setMinimumHeight(50)
        self.btn_defect.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        self.btn_defect.clicked.connect(lambda: self._do_action('defect'))
        actions_layout.addWidget(self.btn_defect)

        self.btn_keep = QPushButton('📌 Оставить')
        self.btn_keep.setProperty('class', 'secondary')
        self.btn_keep.setMinimumHeight(50)
        self.btn_keep.clicked.connect(lambda: self._do_action('keep'))
        actions_layout.addWidget(self.btn_keep)

        self.btn_semifinished = QPushButton('🔧 Полуфабрикат')
        self.btn_semifinished.setProperty('class', 'secondary')
        self.btn_semifinished.setMinimumHeight(50)
        self.btn_semifinished.clicked.connect(lambda: self._do_action('semifinished'))
        actions_layout.addWidget(self.btn_semifinished)

        layout.addWidget(actions_group)

        btn_layout = QHBoxLayout()
        back_btn = QPushButton('← Назад к SN')
        back_btn.setProperty('class', 'secondary')
        back_btn.clicked.connect(lambda: self._go_step(1))
        btn_layout.addWidget(back_btn)
        btn_layout.addStretch()

        reset_btn = QPushButton('🔄 Начать заново')
        reset_btn.setProperty('class', 'secondary')
        reset_btn.clicked.connect(self._reset)
        btn_layout.addWidget(reset_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    def _load_workplaces(self) -> None:
        try:
            session = get_session()
            workplaces = session.query(Workplace).filter(
                Workplace.is_active == True
            ).order_by(Workplace.order).all()

            self.workplace_combo.clear()
            for wp in workplaces:
                self.workplace_combo.addItem(f'{wp.name} ({wp.type_display})', wp.id)
            session.close()
        except Exception as e:
            print(f'Load workplaces error: {e}')

    def _go_step(self, step: int) -> None:
        self.stack.setCurrentIndex(step)

    def _on_worker_scanned(self) -> None:
        worker_code = self.worker_input.text().strip()
        if not worker_code:
            self.worker_status.setText('❌ Введите QR-код или имя работника')
            self.worker_status.setStyleSheet(f'color: {COLORS["error"]};')
            return

        try:
            session = get_session()
            from sqlalchemy import or_
            worker = session.query(User).filter(
                or_(User.username == worker_code, User.first_name == worker_code)
            ).first()

            if not worker:
                self.worker_status.setText(f'❌ Работник "{worker_code}" не найден')
                self.worker_status.setStyleSheet(f'color: {COLORS["error"]};')
                session.close()
                return

            wp_id = self.workplace_combo.currentData()
            workplace = session.query(Workplace).get(wp_id)

            if not workplace:
                self.worker_status.setText('❌ Рабочее место не выбрано')
                self.worker_status.setStyleSheet(f'color: {COLORS["error"]};')
                session.close()
                return

            self.current_worker = worker
            self.current_workplace = workplace

            active = session.query(WorkSession).filter(
                WorkSession.worker_id == worker.id,
                WorkSession.workplace_id == workplace.id,
                WorkSession.is_active == True
            ).first()

            if active:
                self.current_session = active
            else:
                new_session = WorkSession(
                    worker_id=worker.id,
                    workplace_id=workplace.id,
                    started_at=datetime.now(),
                    is_active=True
                )
                session.add(new_session)
                session.commit()
                self.current_session = new_session

            self.step2_info.setText(
                f'👤 {worker.full_name}  ·  🏭 {workplace.name}'
            )
            session.close()
            self._go_step(1)
            self.sn_input.setFocus()

        except Exception as e:
            self.worker_status.setText(f'❌ Ошибка: {str(e)[:50]}')
            self.worker_status.setStyleSheet(f'color: {COLORS["error"]};')

    def _add_to_batch(self):
        try:
            sn_raw = self.sn_input.text().strip()
            self.sn_input.clear()
            
            if not sn_raw:
                return

            if sn_raw.lower() == 'exit':
                self._end_session()
                return

            for s in sn_raw.split():
                if s not in self.scanned_sns:
                    self.scanned_sns.append(s)
                    self.batch_list.addItem(f"✅ {s}")

            self.sn_status.setText(f'В партии: {len(self.scanned_sns)}')
            self.sn_status.setStyleSheet(f'color: {COLORS["text"]};')
        except Exception as e:
            print("Ошибка добавления:", e)

    def _clear_batch(self):
        self.scanned_sns.clear()
        self.batch_list.clear()
        self.sn_status.clear()
        self.sn_input.setFocus()

    def _process_batch(self) -> None:
        if not self.scanned_sns:
            self.sn_status.setText('❌ Партия пуста')
            self.sn_status.setStyleSheet(f'color: {COLORS["error"]};')
            return

        try:
            session = get_session()
            workplace = session.query(Workplace).get(self.current_workplace.id)

            valid_devices = []
            
            for sn in self.scanned_sns:
                device = session.query(Device).filter(Device.serial_number == sn).first()

                if not device:
                    self.sn_status.setText(f'❌ Устройство SN "{sn}" не найдено')
                    self.sn_status.setStyleSheet(f'color: {COLORS["error"]};')
                    session.close()
                    return

                if device.is_semifinished and not workplace.accepts_semifinished:
                    self.sn_status.setText(f'❌ {sn}: Стенд не принимает полуфабрикаты')
                    self.sn_status.setStyleSheet(f'color: {COLORS["error"]};')
                    session.close()
                    return

                if workplace.restrict_same_worker:
                    last_log = session.query(WorkLog).filter(
                        WorkLog.device_id == device.id,
                        WorkLog.action == 'COMPLETED'
                    ).order_by(WorkLog.created_at.desc()).first()

                    if last_log and last_log.worker_id == self.current_worker.id:
                        self.sn_status.setText(f'❌ {sn}: Вы выполняли предыдущий этап. Запрет подряд.')
                        self.sn_status.setStyleSheet(f'color: {COLORS["error"]};')
                        session.close()
                        return
                        
                valid_devices.append(device)

            self.current_devices = valid_devices

            for device in self.current_devices:
                old_status = device.status
                if workplace.device_status_on_enter:
                    device.status = workplace.device_status_on_enter

                device.current_worker_id = self.current_worker.id

                log = WorkLog(
                    worker_id=self.current_worker.id,
                    session_id=self.current_session.id,
                    workplace_id=self.current_workplace.id,
                    device_id=device.id,
                    project_id=device.project_id,
                    action='SCAN_IN',
                    old_status=old_status,
                    new_status=device.status,
                    part_number=device.part_number or '',
                    serial_number=device.serial_number or '',
                    created_at=datetime.now()
                )
                session.add(log)
                
            session.commit()

            self.step3_info.setText(
                f'👤 {self.current_worker.full_name}  ·  '
                f'🏭 {self.current_workplace.name}  ·  '
                f'📦 Устройств в партии: {len(self.current_devices)}'
            )
            
            details = "<b>Отсканированные системы:</b><br>"
            for i, d in enumerate(self.current_devices):
                if i < 10:
                    details += f"— SN: {d.serial_number} ({d.name}) [Статус: {d.status}]<br>"
            if len(self.current_devices) > 10:
                details += f"<i>...и еще {len(self.current_devices) - 10} шт.</i>"
                
            self.device_detail_label.setText(details)

            session.close()
            self._go_step(2)

        except Exception as e:
            self.sn_status.setText(f'❌ Ошибка: {str(e)[:50]}')
            self.sn_status.setStyleSheet(f'color: {COLORS["error"]};')

    def _do_action(self, action: str) -> None:
        STATUS_MAP = {
            'PRE_PRODUCTION': 'ASSEMBLY',
            'ASSEMBLY': 'VIBROSTAND',
            'VIBROSTAND': 'TECH_CONTROL_1_1',
            'TECH_CONTROL_1_1': 'TECH_CONTROL_1_2',
            'TECH_CONTROL_1_2': 'FUNC_CONTROL',
            'FUNC_CONTROL': 'TECH_CONTROL_2_1',
            'TECH_CONTROL_2_1': 'TECH_CONTROL_2_2',
            'TECH_CONTROL_2_2': 'PACKING',
            'PACKING': 'ACCOUNTING',
            'ACCOUNTING': 'QC_PASSED',
        }

        try:
            session = get_session()
            workplace = session.query(Workplace).get(self.current_workplace.id)

            for d in self.current_devices:
                device = session.query(Device).get(d.id)
                old_status = device.status

                if action == 'complete':
                    new_status = STATUS_MAP.get(workplace.workplace_type, 'QC_PASSED')
                    device.status = new_status
                    device.current_worker_id = None
                    action_type = 'COMPLETED'
                elif action == 'in_progress':
                    device.status = workplace.workplace_type
                    action_type = 'IN_PROGRESS'
                elif action == 'defect':
                    device.status = 'DEFECT'
                    device.current_worker_id = None
                    action_type = 'DEFECT'
                elif action == 'keep':
                    action_type = 'KEPT'
                elif action == 'semifinished':
                    device.is_semifinished = True
                    device.current_worker_id = None
                    action_type = 'MAKE_SEMIFINISHED'
                else:
                    continue

                log = WorkLog(
                    worker_id=self.current_worker.id,
                    session_id=self.current_session.id,
                    workplace_id=self.current_workplace.id,
                    device_id=device.id,
                    project_id=device.project_id,
                    action=action_type,
                    old_status=old_status,
                    new_status=device.status,
                    part_number=device.part_number or '',
                    serial_number=device.serial_number or '',
                    created_at=datetime.now()
                )
                session.add(log)

            session.commit()
            session.close()

            action_displays = {
                'COMPLETED': '✅ Готово',
                'IN_PROGRESS': '▶ В работе',
                'DEFECT': '⚠️ Брак',
                'KEPT': '📌 Оставлено',
                'MAKE_SEMIFINISHED': '🔧 Полуфабрикат'
            }
            msg = f'Действие "{action_displays.get(action_type, action_type)}" успешно применено для {len(self.current_devices)} устройств(а).'
            QMessageBox.information(self, 'Успех', msg)
            
            self._reset_to_sn()

        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _reset_to_sn(self) -> None:
        self.current_devices = []
        self._clear_batch()
        self._go_step(1)

    def _end_session(self) -> None:
        try:
            if self.current_session:
                session = get_session()
                ws = session.query(WorkSession).get(self.current_session.id)
                if ws:
                    ws.is_active = False
                    ws.ended_at = datetime.now()
                    session.commit()
                session.close()
        except Exception:
            pass
        self._reset()

    def _reset(self) -> None:
        self.current_worker = None
        self.current_workplace = None
        self.current_session = None
        self.current_devices = []
        self._clear_batch()
        self.worker_input.clear()
        self.worker_status.clear()
        self._go_step(0)
        self.worker_input.setFocus()
