# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Использование hook-файлов (хуки теперь в этой же папке)
hookspath = ['.']

# Скрытые импорты будут добавлены через hook
hiddenimports = [
    'pandas',
    'openpyxl',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'core',
    'core.column_analyzer',
    'core.export_manager',
    'core.parser_factory',
    'core.parser_strategy',
    'core.sql_dialect',
    'core.sql_parser',
    'core.sql_preprocessor',
    'models',
    'models.sql_metadata',
    'ui',
    'ui.main_window',
    'ui.help_text',
]

# Данные
datas = []

# Сборка
a = Analysis(
    ['../app.py'],  # app.py на уровень выше
    pathex=['..'],  # добавляем родительскую директорию в путь поиска модулей
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
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
    a.binaries,
    a.datas,
    [],
    name='SQLparser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Если нужно собрать как однофайловое приложение
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SQLparser',
)