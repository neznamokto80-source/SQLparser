"""
PyQt6 main window for SQL Metadata Parser v4.0.
"""
from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.export_manager import ExportManager
from core.sql_parser import ParserFactory, SQLDialect
from models.sql_metadata import SQLMetadata
from ui.data_presenter import DataPresenter
from ui.examples import get_examples
from ui.export_handler import ExportHandler
from ui.help_dialog import HelpDialog
from ui.parse_worker import ParseWorker
from ui.sql_highlighter import SQLHighlighter
from ui.theme_manager import apply_light_theme, apply_dark_theme
from ui.widget_builder import WidgetBuilder


class MainWindow(QMainWindow):
    """Главное окно приложения SQL Metadata Parser.

    Обеспечивает интерфейс для ввода SQL, выбора диалекта, анализа и просмотра результатов.
    """

    def __init__(self):
        """Инициализирует главное окно, создаёт UI элементы и настраивает стили."""
        super().__init__()
        self.metadata: Optional[SQLMetadata] = None
        self.current_dialect = SQLDialect.ORACLE
        self.export_manager = ExportManager()
        self.example_index = 0  # индекс текущего примера SQL
        self.examples = get_examples()
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        self.setWindowTitle("SQL Metadata Parser v4.0")
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = int(available.width() * 0.8)
            height = int(available.height() * 0.8)
            x = available.x() + (available.width() - width) // 2
            y = available.y() + (available.height() - height) // 2
            self.setGeometry(x, y, width, height)
        else:
            self.setGeometry(100, 100, 1480, 900)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ---- ВЕРХНЯЯ ПАНЕЛЬ С КНОПКОЙ СПРАВКИ И ПЕРЕКЛЮЧАТЕЛЕМ ТЕМЫ ----
        top_layout = QHBoxLayout()
        top_layout.addStretch()  # растяжка, чтобы кнопка ушла вправо
        self.dark_theme_checkbox = QCheckBox("Тёмная тема")
        self.dark_theme_checkbox.stateChanged.connect(self.toggle_dark_theme)
        top_layout.addWidget(self.dark_theme_checkbox)
        help_button = QPushButton("Справка")
        help_button.clicked.connect(self.show_help)
        top_layout.addWidget(help_button)
        # Добавляем верхнюю панель с минимальным stretch (5% высоты)
        root.addLayout(top_layout)
        # -----------------------------------------------------------------

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([600, 800])  # Более сбалансированные пропорции
        # Добавляем splitter с stretch factor 17 (85% высоты)
        root.addWidget(splitter, 17)

        self.info_label = QLabel("Готово к работе. Введите SQL запрос и нажмите «Анализировать SQL».")
        self.info_label.setWordWrap(True)
        # Ограничиваем высоту информационной панели
        self.info_label.setMaximumHeight(60)
        # Добавляем информационную панель с stretch factor 2 (10% высоты)
        root.addWidget(self.info_label, 2)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

        # Горячие клавиши
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.parse_sql)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self.parse_sql)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(lambda: self.export_data("csv"))

    def _build_left_panel(self) -> QWidget:
        """Создает левую панель для ввода SQL запроса.
        
        Returns:
            QGroupBox: Готовая панель с элементами управления
        """
        return WidgetBuilder.build_left_panel(self)

    def _build_right_panel(self) -> QWidget:
        """Создает правую панель для отображения результатов парсинга.
        
        Returns:
            QGroupBox: Готовая панель с вкладками и элементами управления
        """
        return WidgetBuilder.build_right_panel(self)

    def _apply_styles(self) -> None:
        """Применяет светлую тему к приложению."""
        apply_light_theme()

    def toggle_dark_theme(self, state: int) -> None:
        """Переключает тёмную тему интерфейса.

        Args:
            state: Состояние чекбокса (2 для Qt.CheckState.Checked).
        """
        if state == 2:  # Qt.CheckState.Checked
            apply_dark_theme()
        else:
            self._apply_styles()  # вернуть светлую тему

    def _set_dialect(self) -> None:
        self.current_dialect = self.dialect_combo.currentData()

    def toggle_highlighting(self, state: int) -> None:
        """Включает/выключает подсветку синтаксиса SQL.

        Args:
            state: Состояние чекбокса (2 для Qt.CheckState.Checked).
        """
        if state == 2:  # Qt.CheckState.Checked
            self.highlighter.setDocument(self.sql_input.document())
        else:
            self.highlighter.setDocument(None)

    def parse_sql(self) -> None:
        """Запускает асинхронный анализ SQL запроса.

        Извлекает текст из поля ввода, проверяет его непустоту, создаёт прогресс-диалог
        и запускает фоновый поток ParseWorker.
        """
        sql = self.sql_input.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "Внимание", "Введите SQL запрос.")
            return

        self.progress_dialog = QProgressDialog("Анализ SQL...", "Отмена", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.worker = ParseWorker(sql, self.current_dialect)
        self.worker.parse_complete.connect(self.on_parse_complete)
        self.worker.parse_error.connect(self.on_parse_error)
        self.worker.progress_update.connect(self.on_progress)
        self.worker.start()

    def on_progress(self, value: int, text: str) -> None:
        """Обновляет прогресс-диалог.

        Args:
            value: Процент выполнения (0-100).
            text: Текст для отображения.
        """
        self.progress_dialog.setValue(value)
        self.progress_dialog.setLabelText(text)

    def on_parse_complete(self, metadata: SQLMetadata) -> None:
        """Обрабатывает успешное завершение анализа.

        Args:
            metadata: Результаты парсинга SQLMetadata.
        """
        self.progress_dialog.close()
        self.metadata = metadata
        self._populate_result_views()
        self.status_bar.showMessage(
            f"Колонок: {len(metadata.columns)}, таблиц: {len(metadata.get_unique_tables())}, ошибок: {len(metadata.parse_errors)}"
        )
        self.info_label.setText("Анализ завершен. Используйте вкладки справа для просмотра и экспорта результатов.")

    def on_parse_error(self, error: str) -> None:
        """Обрабатывает ошибку анализа.

        Args:
            error: Текст ошибки.
        """
        self.progress_dialog.close()
        QMessageBox.critical(self, "Ошибка", error)
        self.info_label.setText(f"Ошибка анализа: {error}")

    def _populate_result_views(self) -> None:
        """Заполняет все представления результатами парсинга."""
        if not self.metadata:
            return
        
        # Очищаем все представления
        self.tables_tree.clear()
        self.columns_tree.clear()
        self.lineage_tree.clear()
        self.stats_text.clear()
        if hasattr(self, 'text_output'):
            self.text_output.clear()
        
        # Заполняем деревья и текстовые поля с помощью DataPresenter
        DataPresenter.populate_columns_tree(self.columns_tree, self.metadata)
        DataPresenter.populate_tables_tree(self.tables_tree, self.metadata)
        DataPresenter.populate_lineage_tree(self.lineage_tree, self.metadata)
        DataPresenter.populate_stats_text(self.stats_text, self.metadata)
        
        # Обновляем текстовый вывод
        self._update_text_output()

    def _update_text_output(self) -> None:
        """Обновление текстового вывода результатов."""
        if not self.metadata:
            return
        
        text = DataPresenter.generate_text_output(self.metadata, self.current_dialect.value)
        if hasattr(self, 'text_output'):
            self.text_output.setPlainText(text)

    def apply_global_filter(self, text: str) -> None:
        """Фильтрует строки во всех деревьях результатов по введённому тексту.

        Args:
            text: Текст для фильтрации (регистронезависимый).
        """
        filter_text = text.lower()
        trees = [self.tables_tree, self.columns_tree, self.lineage_tree]
        for tree in trees:
            for idx in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(idx)
                visible = any(filter_text in item.text(col).lower() for col in range(item.columnCount()))
                item.setHidden(not visible)

    def export_data(self, fmt: str) -> None:
        """Экспортирует результаты анализа в файл указанного формата.

        Поддерживаемые форматы: "csv", "excel", "text", "json".

        Args:
            fmt: Строка идентификатора формата.
        """
        if not self.metadata:
            QMessageBox.warning(self, "Внимание", "Нет данных для экспорта.")
            return
        
        # Создаем обработчик экспорта и выполняем экспорт
        export_handler = ExportHandler(self, self.status_bar)
        export_handler.export_data(self.metadata, fmt)

    def copy_to_clipboard(self) -> None:
        """Копирует сводку колонок в буфер обмена в формате TSV."""
        if not self.metadata:
            return
        
        # Генерируем текст для буфера обмена с помощью DataPresenter
        clipboard_text = DataPresenter.generate_clipboard_text(self.metadata)
        QApplication.clipboard().setText(clipboard_text)
        
        self.status_bar.showMessage("Скопировано в буфер обмена")
        self.info_label.setText(f"Скопировано строк: {len(self.metadata.column_analysis)}")

    def load_example(self) -> None:
        """Загружает пример SQL запроса в поле ввода, циклически переключаясь между примерами."""
        if not self.examples:
            return
        example = self.examples[self.example_index]
        self.sql_input.setPlainText(example)
        # Увеличиваем индекс для следующего нажатия
        self.example_index = (self.example_index + 1) % len(self.examples)
        # Показываем подсказку в статусной строке
        self.status_bar.showMessage(f"Загружен пример {self.example_index + 1} из {len(self.examples)}")

    def load_from_file(self) -> None:
        """Загружает SQL запрос из файла."""
        path, _ = QFileDialog.getOpenFileName(self, "Выберите SQL", "", "SQL (*.sql *.txt);;Все файлы (*.*)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as fp:
            self.sql_input.setPlainText(fp.read())
        self.info_label.setText(f"Загружен файл: {os.path.basename(path)}")

    def clear_all(self) -> None:
        """Очищает поле ввода SQL и все результаты анализа."""
        self.sql_input.clear()
        self.metadata = None
        self.tables_tree.clear()
        self.columns_tree.clear()
        self.lineage_tree.clear()
        self.stats_text.clear()
        self.info_label.setText("Поле очищено. Введите SQL запрос.")

    def show_help(self) -> None:
        """Отображение окна справки."""
        is_dark_theme = self.dark_theme_checkbox.isChecked()
        HelpDialog.show(self, is_dark_theme)
