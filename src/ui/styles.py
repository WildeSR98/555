"""
QSS стили — тёмная тема для Production Manager.
Премиальный дизайн в стиле современных IDE.
"""

# Цветовая палитра
COLORS = {
    'bg_primary': '#0f1117',
    'bg_secondary': '#1a1b2e',
    'bg_surface': '#252640',
    'bg_elevated': '#2d2e4a',
    'bg_hover': '#363758',
    'bg_input': '#1e1f35',

    'accent': '#6366f1',
    'accent_hover': '#818cf8',
    'accent_pressed': '#4f46e5',

    'text_primary': '#e2e8f0',
    'text_secondary': '#94a3b8',
    'text_muted': '#64748b',

    'border': '#334155',
    'border_focus': '#6366f1',

    'success': '#22c55e',
    'error': '#ef4444',
    'warning': '#f59e0b',
    'info': '#3b82f6',
}

# Статусные цвета для устройств
DEVICE_STATUS_COLORS = {
    'PRE_PRODUCTION': '#6c757d',
    'ASSEMBLY': '#3b82f6',
    'VIBROSTAND': '#06b6d4',
    'TECH_CONTROL_1_1': '#eab308',
    'TECH_CONTROL_1_2': '#eab308',
    'TECH_CONTROL_2_1': '#eab308',
    'TECH_CONTROL_2_2': '#eab308',
    'FUNC_CONTROL': '#f97316',
    'QC_PASSED': '#22c55e',
    'DEFECT': '#ef4444',
    'WAITING_PARTS': '#f59e0b',
    'WAITING_SOFTWARE': '#f59e0b',
    'PACKING': '#14b8a6',
    'ACCOUNTING': '#8b5cf6',
    'SHIPPED': '#059669',
    'ACTIVE': '#22c55e',
    'INACTIVE': '#6b7280',
    'MAINTENANCE': '#f59e0b',
    'BROKEN': '#ef4444',
    'RETIRED': '#374151',
}


def get_main_stylesheet() -> str:
    """Главная таблица стилей приложения."""
    c = COLORS
    return f"""
    /* ===== GLOBAL ===== */
    QMainWindow, QDialog {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
    }}

    QWidget {{
        background-color: transparent;
        color: {c['text_primary']};
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 13px;
    }}

    /* ===== LABELS ===== */
    QLabel {{
        color: {c['text_primary']};
        background: transparent;
    }}

    QLabel[class="title"] {{
        font-size: 22px;
        font-weight: bold;
        color: {c['text_primary']};
    }}

    QLabel[class="subtitle"] {{
        font-size: 15px;
        color: {c['text_secondary']};
    }}

    QLabel[class="muted"] {{
        font-size: 12px;
        color: {c['text_muted']};
    }}

    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: 8px;
        background-color: {c['bg_secondary']};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: {c['bg_surface']};
        color: {c['text_secondary']};
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        min-width: 100px;
    }}

    QTabBar::tab:selected {{
        background-color: {c['bg_secondary']};
        color: {c['accent']};
        border-bottom: 2px solid {c['accent']};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {c['bg_hover']};
        color: {c['text_primary']};
    }}

    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {c['accent']};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        font-weight: 600;
        min-height: 32px;
    }}

    QPushButton:hover {{
        background-color: {c['accent_hover']};
    }}

    QPushButton:pressed {{
        background-color: {c['accent_pressed']};
    }}

    QPushButton:disabled {{
        background-color: {c['bg_surface']};
        color: {c['text_muted']};
    }}

    QPushButton[class="secondary"] {{
        background-color: {c['bg_surface']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
    }}

    QPushButton[class="secondary"]:hover {{
        background-color: {c['bg_hover']};
        border-color: {c['accent']};
    }}

    QPushButton[class="danger"] {{
        background-color: {c['error']};
    }}

    QPushButton[class="danger"]:hover {{
        background-color: #dc2626;
    }}

    QPushButton[class="success"] {{
        background-color: {c['success']};
    }}

    QPushButton[class="success"]:hover {{
        background-color: #16a34a;
    }}

    /* ===== INPUTS ===== */
    QLineEdit, QTextEdit, QSpinBox, QComboBox {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        min-height: 20px;
        selection-background-color: {c['accent']};
    }}

    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {c['border_focus']};
    }}

    QLineEdit:disabled {{
        background-color: {c['bg_surface']};
        color: {c['text_muted']};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 25px;
        border-left: 1px solid {c['border']};
    }}

    QComboBox::down-arrow {{
        /* Встроенный SVG для стрелочки из-за бага отрисовки PyQT при сбросе стилей */
        image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%2394a3b8' viewBox='0 0 16 16'><path d='M4.293 5.293a1 1 0 0 1 1.414 0L8 7.586l2.293-2.293a1 1 0 1 1 1.414 1.414l-3 3a1 1 0 0 1-1.414 0l-3-3a1 1 0 0 1 0-1.414z'/></svg>");
        width: 16px;
        height: 16px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c['bg_elevated']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent']};
    }}

    /* ===== TABLES ===== */
    QTableWidget, QTableView {{
        background-color: {c['bg_secondary']};
        alternate-background-color: {c['bg_surface']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        gridline-color: {c['border']};
        selection-background-color: {c['accent']};
        selection-color: white;
    }}

    QTableWidget::item, QTableView::item {{
        padding: 6px 10px;
        border-bottom: 1px solid {c['border']};
    }}

    QTableWidget::item:hover, QTableView::item:hover {{
        background-color: {c['bg_hover']};
    }}

    QHeaderView::section {{
        background-color: {c['bg_surface']};
        color: {c['text_secondary']};
        padding: 8px 10px;
        border: none;
        border-bottom: 2px solid {c['border']};
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
    }}

    /* ===== TREE VIEW ===== */
    QTreeWidget {{
        background-color: {c['bg_secondary']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        alternate-background-color: {c['bg_surface']};
    }}

    QTreeWidget::item {{
        padding: 6px;
        border-bottom: 1px solid {c['border']};
    }}

    QTreeWidget::item:selected {{
        background-color: {c['accent']};
        color: white;
    }}

    QTreeWidget::item:hover:!selected {{
        background-color: {c['bg_hover']};
    }}

    /* ===== SCROLL BARS ===== */
    QScrollBar:vertical {{
        background-color: {c['bg_primary']};
        width: 10px;
        margin: 0;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {c['bg_hover']};
        min-height: 30px;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {c['text_muted']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: {c['bg_primary']};
        height: 10px;
        margin: 0;
        border-radius: 5px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {c['bg_hover']};
        min-width: 30px;
        border-radius: 5px;
    }}

    /* ===== STATUS BAR ===== */
    QStatusBar {{
        background-color: {c['bg_surface']};
        color: {c['text_secondary']};
        border-top: 1px solid {c['border']};
        font-size: 12px;
    }}

    QStatusBar QLabel {{
        padding: 2px 8px;
    }}

    /* ===== MENU BAR ===== */
    QMenuBar {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border-bottom: 1px solid {c['border']};
        padding: 2px;
    }}

    QMenuBar::item {{
        padding: 6px 12px;
        border-radius: 4px;
    }}

    QMenuBar::item:selected {{
        background-color: {c['bg_hover']};
    }}

    QMenu {{
        background-color: {c['bg_elevated']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {c['accent']};
        color: white;
    }}

    /* ===== GROUP BOX ===== */
    QGroupBox {{
        background-color: {c['bg_surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 20px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        color: {c['text_secondary']};
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}

    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {c['bg_input']};
        border: none;
        border-radius: 4px;
        text-align: center;
        color: white;
        font-size: 11px;
        height: 18px;
    }}

    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: 4px;
    }}

    /* ===== SPLITTER ===== */
    QSplitter::handle {{
        background-color: {c['border']};
    }}

    QSplitter::handle:horizontal {{
        width: 2px;
    }}

    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ===== FRAME CARDS ===== */
    QFrame[class="card"] {{
        background-color: {c['bg_surface']};
        border: 1px solid {c['border']};
        border-radius: 12px;
        padding: 16px;
    }}

    QFrame[class="card-elevated"] {{
        background-color: {c['bg_elevated']};
        border: 1px solid {c['border']};
        border-radius: 12px;
        padding: 16px;
    }}

    QFrame[class="card"]:hover {{
        border-color: {c['accent']};
    }}
    """


def get_login_stylesheet() -> str:
    """Стили для окна логина."""
    c = COLORS
    return f"""
    QDialog {{
        background-color: {c['bg_primary']};
    }}

    QLabel#loginTitle {{
        font-size: 28px;
        font-weight: bold;
        color: {c['text_primary']};
    }}

    QLabel#loginSubtitle {{
        font-size: 14px;
        color: {c['text_secondary']};
    }}

    QLineEdit {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 14px;
        min-height: 24px;
    }}

    QLineEdit:focus {{
        border-color: {c['accent']};
    }}

    QPushButton#loginBtn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['accent']}, stop:1 #8b5cf6);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 14px;
        font-size: 15px;
        font-weight: 700;
        min-height: 28px;
    }}

    QPushButton#loginBtn:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['accent_hover']}, stop:1 #a78bfa);
    }}

    QPushButton#loginBtn:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['accent_pressed']}, stop:1 #7c3aed);
    }}

    QLabel#errorLabel {{
        color: {c['error']};
        font-size: 12px;
    }}

    QLabel#dbStatus {{
        color: {c['text_muted']};
        font-size: 11px;
    }}
    """
