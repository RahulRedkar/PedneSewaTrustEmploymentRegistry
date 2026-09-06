# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/Pedne Sewa Trust Employment Related Data/main.py'],
    pathex=[],
    binaries=[],
    datas=[('E:/Pedne Sewa Trust Employment Related Data/assets/logo.png', 'assets'), ('E:/Pedne Sewa Trust Employment Related Data/assets/icon.ico', 'assets'), ('E:/Pedne Sewa Trust Employment Related Data/assets/styles.qss', 'assets')],
    hiddenimports=['app.version', 'requests', 'sync.apps_script_client', 'database.demo_data_generator', 'reportlab', 'reportlab.lib', 'reportlab.lib.pagesizes', 'reportlab.lib.colors', 'reportlab.platypus', 'reportlab.pdfgen', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'sqlite3', 'models.facilitation', 'models.candidate', 'facilitation.job_adapters', 'facilitation.matching_engine', 'facilitation.recruiter_service', 'facilitation.document_manager', 'app.updater'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PedneSewaTrustRegistry',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:/Pedne Sewa Trust Employment Related Data/assets/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PedneSewaTrustRegistry',
)
