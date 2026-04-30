"""
Фабрика UI компонентов для SQL Metadata Parser.

Содержит методы для создания стандартизированных UI элементов,
что позволяет уменьшить дублирование кода в main_window.py.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.sql_parser import SQLDialect
from ui.sql_highlighter import SQLHighlighter


class WidgetBuilder:
    """Класс-фабрика для создания UI компонентов."""
    
    @staticmethod
    def build_left_panel(parent) -> QWidget:
        """Создает левую панель для ввода SQL запроса.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QGroupBox: Готовая панель с элементами управления
        """
        panel = QGroupBox("Ввод SQL запроса")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        btn_example = QPushButton("📋 Пример SQL")
        btn_example.clicked.connect(parent.load_example)
        buttons.addWidget(btn_example)

        btn_load = QPushButton("📁 Загрузить")
        btn_load.clicked.connect(parent.load_from_file)
        buttons.addWidget(btn_load)

        btn_clear = QPushButton("🗑 Очистить")
        btn_clear.clicked.connect(parent.clear_all)
        buttons.addWidget(btn_clear)
        
        buttons.addStretch()
        
        parent.highlight_checkbox = QCheckBox("Подсветка синтаксиса")
        parent.highlight_checkbox.setChecked(True)
        parent.highlight_checkbox.stateChanged.connect(parent.toggle_highlighting)
        buttons.addWidget(parent.highlight_checkbox)
        
        layout.addLayout(buttons)

        parent.sql_input = QTextEdit()
        parent.sql_input.setFont(QFont("Courier New", 10))
        parent.sql_input.setPlaceholderText("Вставьте SQL здесь...")
        # Подсветка синтаксиса SQL
        parent.highlighter = SQLHighlighter(parent.sql_input.document())
        layout.addWidget(parent.sql_input)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Диалект:"))
        parent.dialect_combo = QComboBox()
        parent.dialect_combo.addItem("Oracle", SQLDialect.ORACLE)
        parent.dialect_combo.addItem("PostgreSQL", SQLDialect.POSTGRESQL)
        parent.dialect_combo.addItem("MySQL", SQLDialect.MYSQL)
        parent.dialect_combo.addItem("SQL Server", SQLDialect.SQLSERVER)
        parent.dialect_combo.addItem("Snowflake", SQLDialect.SNOWFLAKE)
        parent.dialect_combo.currentIndexChanged.connect(lambda _: parent._set_dialect())
        bottom.addWidget(parent.dialect_combo)
        bottom.addStretch()

        parse_btn = QPushButton("📊 Анализировать SQL")
        parse_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        parse_btn.clicked.connect(parent.parse_sql)
        bottom.addWidget(parse_btn)
        layout.addLayout(bottom)
        return panel

    @staticmethod
    def build_right_panel(parent) -> QWidget:
        """Создает правую панель для отображения результатов парсинга.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QGroupBox: Готовая панель с вкладками и элементами управления
        """
        panel = QGroupBox("Результаты парсинга")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Общий фильтр:"))
        parent.global_filter = QLineEdit()
        parent.global_filter.setPlaceholderText("Введите текст для фильтрации всех вкладок...")
        parent.global_filter.textChanged.connect(parent.apply_global_filter)
        filter_layout.addWidget(parent.global_filter)
        clear_filter_btn = QPushButton("Очистить")
        clear_filter_btn.clicked.connect(lambda: parent.global_filter.clear())
        filter_layout.addWidget(clear_filter_btn)
        layout.addLayout(filter_layout)

        parent.tabs = QTabWidget()
        parent.tabs.addTab(WidgetBuilder.create_columns_tab(parent), "Колонки")
        parent.tabs.addTab(WidgetBuilder.create_tables_tab(parent), "Таблицы")
        parent.tabs.addTab(WidgetBuilder.create_lineage_tab(parent), "Линедж")
        parent.tabs.addTab(WidgetBuilder.create_stats_tab(parent), "Статистика")
        parent.tabs.addTab(WidgetBuilder.create_text_output_tab(parent), "Текстовый вывод")
        layout.addWidget(parent.tabs)

        actions = QHBoxLayout()
        copy_btn = QPushButton("📋 Копировать в буфер")
        copy_btn.clicked.connect(parent.copy_to_clipboard)
        actions.addWidget(copy_btn)
        actions.addStretch()

        csv_btn = QPushButton("📊 Экспорт CSV")
        csv_btn.clicked.connect(lambda: parent.export_data("csv"))
        actions.addWidget(csv_btn)

        excel_btn = QPushButton("📗 Экспорт Excel")
        excel_btn.clicked.connect(lambda: parent.export_data("excel"))
        actions.addWidget(excel_btn)

        txt_btn = QPushButton("📝 Экспорт TXT")
        txt_btn.clicked.connect(lambda: parent.export_data("text"))
        actions.addWidget(txt_btn)

        json_btn = QPushButton("📤 Экспорт JSON")
        json_btn.clicked.connect(lambda: parent.export_data("json"))
        actions.addWidget(json_btn)
        layout.addLayout(actions)
        return panel

    @staticmethod
    def create_tables_tab(parent) -> QWidget:
        """Создает вкладку для отображения таблиц.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QWidget: Виджет вкладки с деревом таблиц
        """
        w = QWidget()
        l = QVBoxLayout(w)
        parent.tables_tree = QTreeWidget()
        parent.tables_tree.setHeaderLabels(["Схема", "Таблица", "Алиасы", "Тип", "Колонок", "Тип JOIN"])
        parent.tables_tree.setSortingEnabled(True)
        parent.tables_tree.setColumnWidth(0, 110)
        parent.tables_tree.setColumnWidth(1, 190)
        parent.tables_tree.setColumnWidth(2, 200)
        parent.tables_tree.setColumnWidth(3, 130)
        parent.tables_tree.setColumnWidth(4, 80)
        parent.tables_tree.setColumnWidth(5, 120)
        parent.tables_tree.setColumnWidth(4, 90)
        l.addWidget(parent.tables_tree)
        return w

    @staticmethod
    def create_columns_tab(parent) -> QWidget:
        """Создает вкладку для отображения колонок.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QWidget: Виджет вкладки с деревом колонок
        """
        w = QWidget()
        l = QVBoxLayout(w)
        parent.columns_tree = QTreeWidget()
        parent.columns_tree.setHeaderLabels(
            ["Колонка", "Полное имя колонки", "Схема", "Таблица", "Алиас таблицы", "Тип объекта", "Алиасы", "Где используется", "Количество упоминаний"]
        )
        parent.columns_tree.setSortingEnabled(True)
        parent.columns_tree.setColumnWidth(0, 120)   # Колонка
        parent.columns_tree.setColumnWidth(1, 220)   # Полное имя колонки
        parent.columns_tree.setColumnWidth(2, 80)    # Схема
        parent.columns_tree.setColumnWidth(3, 120)   # Таблица
        parent.columns_tree.setColumnWidth(4, 100)   # Алиас таблицы
        parent.columns_tree.setColumnWidth(5, 100)   # Тип объекта
        parent.columns_tree.setColumnWidth(6, 180)   # Алиасы
        parent.columns_tree.setColumnWidth(7, 200)   # Где используется
        parent.columns_tree.setColumnWidth(8, 140)   # Количество упоминаний
        l.addWidget(parent.columns_tree)
        return w

    @staticmethod
    def create_lineage_tab(parent) -> QWidget:
        """Создает вкладку для отображения линеджа.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QWidget: Виджет вкладки с деревом линеджа
        """
        w = QWidget()
        l = QVBoxLayout(w)
        parent.lineage_tree = QTreeWidget()
        parent.lineage_tree.setHeaderLabels(["Колонка", "Таблица", "Источник", "Зависимости", "Использование"])
        parent.lineage_tree.setSortingEnabled(True)
        parent.lineage_tree.setColumnWidth(0, 170)
        parent.lineage_tree.setColumnWidth(1, 150)
        parent.lineage_tree.setColumnWidth(2, 190)
        parent.lineage_tree.setColumnWidth(3, 220)
        parent.lineage_tree.setColumnWidth(4, 300)
        l.addWidget(parent.lineage_tree)
        return w

    @staticmethod
    def create_stats_tab(parent) -> QWidget:
        """Создает вкладку для отображения статистики.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QWidget: Виджет вкладки с текстовым полем статистики
        """
        w = QWidget()
        l = QVBoxLayout(w)
        parent.stats_text = QTextEdit()
        parent.stats_text.setReadOnly(True)
        parent.stats_text.setFont(QFont("Arial", 10))
        l.addWidget(parent.stats_text)
        return w

    @staticmethod
    def create_text_output_tab(parent) -> QWidget:
        """Создает вкладку с текстовым выводом результатов.
        
        Args:
            parent: Родительский виджет (MainWindow)
            
        Returns:
            QWidget: Виджет вкладки с текстовым полем вывода
        """
        w = QWidget()
        l = QVBoxLayout(w)
        parent.text_output = QTextEdit()
        parent.text_output.setReadOnly(True)
        parent.text_output.setFont(QFont("Courier New", 10))
        l.addWidget(parent.text_output)
        return w