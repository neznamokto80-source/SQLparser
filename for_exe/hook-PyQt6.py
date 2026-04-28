# hook for PyQt6
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('PyQt6')
datas = collect_data_files('PyQt6', include_py_files=True)

# Include Qt plugins
# from PyInstaller.utils.hooks.qt import add_qt6_dependencies
# hiddenimports, datas, binaries = add_qt6_dependencies(__file__)
binaries = []