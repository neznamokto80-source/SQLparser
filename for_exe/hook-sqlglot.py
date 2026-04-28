# hook for sqlglot
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('sqlglot')
datas = collect_data_files('sqlglot')

# Include dialect files
import os
import sqlglot
sqlglot_dir = os.path.dirname(sqlglot.__file__)
dialects_dir = os.path.join(sqlglot_dir, 'dialects')
if os.path.exists(dialects_dir):
    for root, dirs, files in os.walk(dialects_dir):
        for file in files:
            if file.endswith('.py'):
                rel_path = os.path.relpath(os.path.join(root, file), sqlglot_dir)
                datas.append((os.path.join(root, file), os.path.join('sqlglot', os.path.dirname(rel_path))))