"""
Вкладка Конвейер — визуальный обзор производственного процесса.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QTimer

from ..database import get_session
from ..models import Device
from .styles import COLORS
from .widgets.pipeline_card import PipelineCard


class PipelineTab(QWidget):
    """Вкладка Конвейер."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.cards: dict[str, PipelineCard] = {}
        self._setup_ui()
        self.refresh_data()

        # Авто-обновление каждые 15 сек
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(15000)

    def _setup_ui(self) -> None:
        """Настройка интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel('🔧 Производственный конвейер')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        self.total_label = QLabel('Всего: 0')
        self.total_label.setStyleSheet(f'font-size: 14px; color: {COLORS["text_secondary"]};')
        header.addWidget(self.total_label)

        refresh_btn = QPushButton('⟳ Обновить')
        refresh_btn.setProperty('class', 'secondary')
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Splitter: карточки | таблица деталей
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Карточки этапов
        cards_widget = QWidget()
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_scroll.setStyleSheet('QScrollArea { border: none; }')

        cards_inner = QWidget()
        self.cards_grid = QGridLayout(cards_inner)
        self.cards_grid.setSpacing(12)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)

        # Добавляем метку "КОНВЕЙЕР"
        conv_label = QLabel('КОНВЕЙЕР ➜')
        conv_label.setStyleSheet(f'font-size: 11px; font-weight: bold; color: {COLORS["text_muted"]};')
        conv_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_grid.addWidget(conv_label, 0, 0, 2, 1)

        # Основной конвейер (статусы ожидания и работы)
        main_stages = [
            ('WAITING_KITTING', 'WAITING_PRE_PRODUCTION', 'Комплектовка'),
            ('WAITING_PRE_PRODUCTION', 'PRE_PRODUCTION', 'Подготовка'),
            ('WAITING_ASSEMBLY', 'ASSEMBLY', 'Сборка'),
            ('WAITING_VIBROSTAND', 'VIBROSTAND', 'Вибростенд'),
            ('WAITING_TECH_CONTROL_1_1', 'TECH_CONTROL_1_1', 'ОТК 1.1'),
            ('WAITING_TECH_CONTROL_1_2', 'TECH_CONTROL_1_2', 'ОТК 1.2'),
            ('WAITING_FUNC_CONTROL', 'FUNC_CONTROL', 'Тестирование'),
            ('WAITING_TECH_CONTROL_2_1', 'TECH_CONTROL_2_1', 'ОТК 2.1'),
            ('WAITING_TECH_CONTROL_2_2', 'TECH_CONTROL_2_2', 'ОТК 2.2'),
            ('WAITING_PACKING', 'PACKING', 'Упаковка'),
            ('WAITING_ACCOUNTING', 'ACCOUNTING', 'Учёт'),
        ]



        for col, (w_code, i_code, label) in enumerate(main_stages, start=1):
            # Карточка ожидания (маленькая)
            w_card = PipelineCard(w_code, f"Ожид. {label}")
            w_card.setMinimumHeight(60)
            w_card.clicked.connect(self._on_stage_clicked)
            self.cards[w_code] = w_card
            self.cards_grid.addWidget(w_card, 0, col)

            # Карточка в работе (основная)
            i_card = PipelineCard(i_code, label)
            i_card.clicked.connect(self._on_stage_clicked)
            self.cards[i_code] = i_card
            self.cards_grid.addWidget(i_card, 1, col)

        # Дополнительные статусы (строка 1)
        extra_stages = [
            ('QC_PASSED', 'Контроль пройден'),
            ('SHIPPED', 'Отгружено'),
            ('DEFECT', 'Брак'),
            ('WAITING_PARTS', 'Ожидание запчастей'),
            ('WAITING_SOFTWARE', 'Ожидание ПО'),
        ]

        extra_label = QLabel('СТАТУСЫ ↓')
        extra_label.setStyleSheet(f'font-size: 11px; font-weight: bold; color: {COLORS["text_muted"]};')
        extra_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_grid.addWidget(extra_label, 2, 0)

        for col, (code, label) in enumerate(extra_stages, start=1):
            card = PipelineCard(code, label)
            card.clicked.connect(self._on_stage_clicked)
            self.cards[code] = card
            self.cards_grid.addWidget(card, 2, col)

        cards_scroll.setWidget(cards_inner)
        splitter.addWidget(cards_scroll)

        # Таблица устройств на выбранном этапе
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 8, 0, 0)

        self.stage_label = QLabel('Выберите этап для просмотра устройств')
        self.stage_label.setStyleSheet(f'font-size: 14px; font-weight: 600; color: {COLORS["text_secondary"]};')
        details_layout.addWidget(self.stage_label)

        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(6)
        self.devices_table.setHorizontalHeaderLabels([
            'Код', 'Название', 'SN', 'PN', 'Проект', 'Работник'
        ])
        hdr = self.devices_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Код
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Название
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # SN
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # PN
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)           # Проект
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Работник
        self.devices_table.setAlternatingRowColors(True)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.devices_table.verticalHeader().setVisible(False)
        details_layout.addWidget(self.devices_table)

        splitter.addWidget(details_widget)
        splitter.setSizes([250, 300])

        layout.addWidget(splitter)

    def refresh_data(self) -> None:
        """Обновление количеств на карточках."""
        try:
            session = get_session()

            total = 0
            for code, card in self.cards.items():
                count = session.query(Device).filter(Device.status == code).count()
                card.update_count(count)
                total += count

            self.total_label.setText(f'Всего на конвейере: {total}')
            session.close()
        except Exception as e:
            print(f'Pipeline refresh error: {e}')

    def _on_stage_clicked(self, status_code: str) -> None:
        """Показать устройства на выбранном этапе."""
        stage_name = Device.STATUS_DISPLAY.get(status_code, status_code)
        self.stage_label.setText(f'📋 Устройства — {stage_name}')

        try:
            session = get_session()

            devices = session.query(Device).filter(
                Device.status == status_code
            ).order_by(Device.name).limit(100).all()

            self.devices_table.setRowCount(len(devices))
            for i, dev in enumerate(devices):
                self.devices_table.setItem(i, 0, QTableWidgetItem(dev.code or '—'))
                self.devices_table.setItem(i, 1, QTableWidgetItem(dev.name))
                self.devices_table.setItem(i, 2, QTableWidgetItem(dev.serial_number or '—'))
                self.devices_table.setItem(i, 3, QTableWidgetItem(dev.part_number or '—'))
                self.devices_table.setItem(i, 4, QTableWidgetItem(
                    dev.project.name if dev.project else '—'
                ))
                self.devices_table.setItem(i, 5, QTableWidgetItem(
                    dev.current_worker.full_name if dev.current_worker else '—'
                ))

            session.close()
        except Exception as e:
            print(f'Stage click error: {e}')
