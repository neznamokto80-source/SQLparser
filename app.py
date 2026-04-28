from __future__ import annotations

import sys
import importlib.util

from PyQt6.QtWidgets import QApplication

# Проверка наличия обязательных библиотек
required_modules = [
    ("sqlglot", "sqlglot", "sqlglot>=24.0.0"),
    ("openpyxl", "openpyxl", "openpyxl>=3.1.0"),
    ("pandas", "pandas", "pandas>=2.0.0"),
    ("networkx", "networkx", "networkx>=3.0"),
    ("matplotlib", "matplotlib", "matplotlib>=3.7"),
]

import subprocess
import os

missing = []
for module_name, package_name, requirement in required_modules:
    if importlib.util.find_spec(module_name) is None:
        missing.append(package_name)

if missing:
    print("Обнаружены отсутствующие библиотеки:", file=sys.stderr)
    for pkg in missing:
        print(f"  - {pkg}", file=sys.stderr)
    print("\nПытаюсь установить автоматически...", file=sys.stderr)
    
    # Попытка установки через pip
    try:
        # Используем pip install --user для избежания прав администратора
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--user"
        ] + missing)
        print("Установка успешно завершена.", file=sys.stderr)
        # После установки перезагружаем интерпретатор? Не требуется, но нужно обновить sys.path
        import site
        site.main()
    except subprocess.CalledProcessError as e:
        print(f"Не удалось установить библиотеки автоматически (код {e.returncode}).", file=sys.stderr)
        print("Пожалуйста, установите зависимости вручную:", file=sys.stderr)
        print(f"  pip install {' '.join(missing)}", file=sys.stderr)
        
        # Попытка показать всплывающее окно с ошибкой
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            # Создаём временное приложение
            app = QApplication(sys.argv)
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Ошибка установки зависимостей")
            msg_box.setText("Не удалось автоматически установить необходимые библиотеки.")
            msg_box.setInformativeText(
                f"Отсутствуют: {', '.join(missing)}\n\n"
                "Установите их вручную через командную строку:\n"
                f"pip install {' '.join(missing)}"
            )
            msg_box.exec()
        except Exception:
            # Если не удалось создать GUI, просто выходим
            pass
        sys.exit(1)

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SQL Metadata Parser")
    app.setApplicationVersion("4.0")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
