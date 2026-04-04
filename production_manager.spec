# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),
        ('db.sqlite3', '.'),
    ],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'src',
        'src.config',
        'src.database',
        'src.models',
        'src.ui',
        'src.ui.styles',
        'src.ui.login_dialog',
        'src.ui.main_window',
        'src.ui.dashboard_tab',
        'src.ui.projects_tab',
        'src.ui.pipeline_tab',
        'src.ui.scan_tab',
        'src.ui.device_status_tab',
        'src.ui.analytics_tab',
        'src.ui.sn_pool_tab',
        'src.ui.admin_tab',
        'src.ui.widgets',
        'src.ui.widgets.pipeline_card',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends',
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_agg',
        'matplotlib.figure',
        'matplotlib.patches',
        'matplotlib.transforms',
        'matplotlib.ticker',
        'matplotlib.font_manager',
        'matplotlib.colors',
        'matplotlib.cm',
        'matplotlib.style',
        'matplotlib.dates',
        'matplotlib.axes',
        'matplotlib.axis',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProductionManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ProductionManager',
)
