"""
PyQt6 main window for SQL Metadata Parser v4.0.
"""
from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QKeySequence, QShortcut, QPixmap
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
    QScrollArea,
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
from ui.help_text import HELP_TEXT


class SQLHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса SQL для QTextEdit."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Формат для ключевых слов SQL
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#007acc"))  # синий
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        keywords = [
            "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
            "ON", "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS", "NULL",
            "GROUP BY", "ORDER BY", "HAVING", "DISTINCT", "AS", "UNION", "ALL",
            "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "CREATE",
            "TABLE", "VIEW", "INDEX", "DROP", "ALTER", "ADD", "COLUMN", "PRIMARY",
            "KEY", "FOREIGN", "REFERENCES", "CONSTRAINT", "DEFAULT", "CHECK",
            "UNIQUE", "ASC", "DESC", "LIMIT", "OFFSET", "TOP", "FETCH", "NEXT",
            "CASE", "WHEN", "THEN", "ELSE", "END", "EXISTS", "ANY", "ALL", "SOME",
            "WITH", "RECURSIVE", "OVER", "PARTITION BY", "ROW_NUMBER", "RANK",
            "DENSE_RANK", "LEAD", "LAG", "FIRST_VALUE", "LAST_VALUE", "NTILE",
            "CAST", "CONVERT", "COALESCE", "NULLIF", "IFNULL", "NVL", "DECODE",
            "EXTRACT", "DATE", "TIME", "TIMESTAMP", "INTERVAL", "YEAR", "MONTH",
            "DAY", "HOUR", "MINUTE", "SECOND", "CURRENT_DATE", "CURRENT_TIME",
            "CURRENT_TIMESTAMP", "NOW", "SYSDATE", "GETDATE", "CURRENT_USER",
            "SESSION_USER", "SYSTEM_USER", "ROLE", "GRANT", "REVOKE", "COMMIT",
            "ROLLBACK", "SAVEPOINT", "BEGIN", "END", "TRANSACTION", "LOCK",
            "UNLOCK", "EXPLAIN", "ANALYZE", "OPTIMIZE", "VACUUM", "TRUNCATE",
            "MERGE", "UPSERT", "RETURNING", "OUTPUT", "EXEC", "EXECUTE", "CALL",
            "PROCEDURE", "FUNCTION", "TRIGGER", "EVENT", "SCHEDULE", "BACKUP",
            "RESTORE", "CHECKPOINT", "SHUTDOWN", "STARTUP", "ARCHIVE", "PURGE",
            "FLUSH", "RESET", "SET", "SHOW", "DESCRIBE", "DESC", "HELP", "USE",
            "DATABASE", "SCHEMA", "OWNER", "TABLESPACE", "CLUSTER", "REPLICATION",
            "SLAVE", "MASTER", "BINARY", "VARBINARY", "CHAR", "VARCHAR", "TEXT",
            "NCHAR", "NVARCHAR", "NTEXT", "INT", "INTEGER", "BIGINT", "SMALLINT",
            "TINYINT", "DECIMAL", "NUMERIC", "FLOAT", "REAL", "DOUBLE", "BOOLEAN",
            "DATE", "DATETIME", "TIMESTAMP", "TIME", "YEAR", "INTERVAL", "BLOB",
            "CLOB", "NCLOB", "XML", "JSON", "ARRAY", "MAP", "STRUCT", "UNIONTYPE",
            "TRUE", "FALSE", "UNKNOWN", "DEFAULT", "AUTO_INCREMENT", "IDENTITY",
            "SEQUENCE", "CASCADE", "RESTRICT", "NO ACTION", "SET NULL", "SET DEFAULT",
            "MATCH", "FULL", "PARTIAL", "SIMPLE", "DEFERRABLE", "IMMEDIATE",
            "INITIALLY", "DEFERRED", "LOCAL", "GLOBAL", "SESSION", "TRANSIENT",
            "TEMPORARY", "TEMP", "VOLATILE", "IMMUTABLE", "STABLE", "VOLUME",
            "COMPRESS", "ENCRYPT", "DECRYPT", "SIGN", "VERIFY", "HASH", "MAC",
            "CIPHER", "KEY", "SECRET", "TOKEN", "CERTIFICATE", "CREDENTIAL",
            "PRIVILEGE", "ROLE", "USER", "PASSWORD", "ACCOUNT", "LOCK", "UNLOCK",
            "EXPIRE", "NEVER", "DEFAULT", "PROFILE", "QUOTA", "LIMIT", "MAX",
            "MIN", "SUM", "AVG", "COUNT", "STDDEV", "VARIANCE", "CORR", "COVAR",
            "REGR", "PERCENTILE", "MEDIAN", "MODE", "RANGE", "STDDEV_POP",
            "STDDEV_SAMP", "VAR_POP", "VAR_SAMP", "COVAR_POP", "COVAR_SAMP",
            "CORR", "REGR_SLOPE", "REGR_INTERcept", "REGR_COUNT", "REGR_R2",
            "REGR_AVGX", "REGR_AVGY", "REGR_SXX", "REGR_SYY", "REGR_SXY",
        ]
        
        for keyword in keywords:
            pattern = QRegularExpression(rf"\b{keyword}\b", QRegularExpression.PatternOption.CaseInsensitiveOption)
            self.highlighting_rules.append((pattern, keyword_format))
        
        # Формат для строк в одинарных и двойных кавычках
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#a31515"))  # темно-красный
        self.highlighting_rules.append((QRegularExpression(r"'.*?'"), string_format))
        self.highlighting_rules.append((QRegularExpression(r'".*?"'), string_format))
        
        # Формат для чисел
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#098658"))  # зеленый
        self.highlighting_rules.append((QRegularExpression(r"\b\d+\b"), number_format))
        self.highlighting_rules.append((QRegularExpression(r"\b\d+\.\d+\b"), number_format))
        
        # Формат для комментариев (однострочных -- и многострочных /* */)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))  # серо-зеленый
        self.highlighting_rules.append((QRegularExpression(r"--[^\n]*"), comment_format))
        self.highlighting_rules.append((QRegularExpression(r"/\*.*?\*/", QRegularExpression.PatternOption.DotMatchesEverythingOption), comment_format))
        
        # Формат для функций (имена функций, за которыми идет открывающая скобка)
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#795e26"))  # коричневый
        function_format.setFontItalic(True)
        self.highlighting_rules.append((QRegularExpression(r"\b\w+(?=\()"), function_format))
        
        # Формат для операторов ( =, <>, !=, <, >, <=, >=, +, -, *, /, %, ||, &, |, ^, ~ )
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#0000ff"))  # синий
        operator_format.setFontWeight(QFont.Weight.Bold)
        operators = ["=", "<>", "!=", "<", ">", "<=", ">=", r"\+", "-", r"\*", "/", "%", r"\|\|", "&", r"\|", r"\^", "~"]
        for op in operators:
            pattern = QRegularExpression(rf"\{op}" if len(op) > 1 else op)
            self.highlighting_rules.append((pattern, operator_format))
    
    def highlightBlock(self, text: str) -> None:
        """Применить правила подсветки к блоку текста."""
        for pattern, fmt in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
        
        # Обработка многострочных комментариев (если начало комментария в предыдущем блоке)
        self.setCurrentBlockState(0)
        
        start_index = 0
        if self.previousBlockState() != 1:
            match = QRegularExpression(r"/\*").match(text)
            start_index = match.capturedStart() if match.hasMatch() else -1
        
        while start_index >= 0:
            end_match = QRegularExpression(r"\*/").match(text, start_index)
            end_index = end_match.capturedStart()
            comment_length = 0
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + 2
            
            comment_format = QTextCharFormat()
            comment_format.setForeground(QColor("#6a9955"))
            self.setFormat(start_index, comment_length, comment_format)
            # Поиск следующего начала комментария
            next_match = QRegularExpression(r"/\*").match(text, start_index + comment_length)
            start_index = next_match.capturedStart() if next_match.hasMatch() else -1


class ParseWorker(QThread):
    """Фоновый поток для асинхронного анализа SQL запроса."""

    parse_complete = pyqtSignal(SQLMetadata)
    parse_error = pyqtSignal(str)
    progress_update = pyqtSignal(int, str)

    def __init__(self, sql: str, dialect: SQLDialect):
        """Инициализирует поток с SQL запросом и диалектом.

        Args:
            sql: SQL запрос для анализа.
            dialect: Диалект SQL (например, SQLDialect.ORACLE).
        """
        super().__init__()
        self.sql = sql
        self.dialect = dialect

    def run(self) -> None:
        """Выполняет анализ SQL в фоновом потоке, отправляет прогресс и результат."""
        try:
            self.progress_update.emit(20, "Подготовка парсера...")
            parser = ParserFactory.create_parser("sqlglot", dialect=self.dialect)
            self.progress_update.emit(60, "Анализ AST...")
            metadata = parser.parse(self.sql)
            self.progress_update.emit(100, "Готово")
            self.parse_complete.emit(metadata)
        except Exception as exc:
            import traceback
            error_msg = str(exc)
            traceback_str = traceback.format_exc()
            # Печать в консоль для отладки
            print(f"ParseWorker error: {error_msg}")
            print(traceback_str)
            self.parse_error.emit(error_msg)


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
        self.examples = [
            # Пример 1: сложный запрос с несколькими алиасами
            """-- Пример сложного SQL запроса с несколькими алиасами
SELECT
    u.id AS user_id,
    u.name AS user_name,
    u.email,
    d.department_name,
    COUNT(o.order_id) as total_orders,
    SUM(o.amount) as total_amount,
    AVG(o.amount) as avg_order_amount
FROM users u
INNER JOIN departments d ON u.dept_id = d.id
LEFT JOIN orders o ON u.id = o.user_id
LEFT JOIN (SELECT table2.t2, table2.t3 FROM table2) tt ON tt.t2 = o.user_id
LEFT JOIN table3 t3a ON t3a.id = u.id
LEFT JOIN table3 t3b ON t3b.id = d.id
WHERE u.active = 1
    AND d.location IN ('Moscow', 'Saint-Petersburg')
    AND o.order_date >= DATE '2023-01-01'
GROUP BY u.id, u.name, u.email, d.department_name
HAVING COUNT(o.order_id) > 5
    AND SUM(o.amount) > 10000
ORDER BY total_amount DESC, user_name ASC""",
            # Пример 2: линейный вариант с оконными функциями и скользящим средним
            """-- Линейный вариант: топ-3 сотрудников по отделам + скользящее среднее (3 последних по дате найма)
WITH
-- 1. Скользящее среднее зарплаты (3 последних сотрудника в отделе по hire_date)
moving_avg AS (
    SELECT
        e1.employee_id,
        AVG(e2.salary) AS moving_avg_salary
    FROM employees e1
    JOIN employees e2
        ON e1.department_id = e2.department_id
        AND e2.hire_date <= e1.hire_date
    WHERE (
        SELECT COUNT(*)
        FROM employees e3
        WHERE e3.department_id = e1.department_id
          AND e3.hire_date BETWEEN e2.hire_date AND e1.hire_date
    ) <= 3   -- последние 3 сотрудника (включая текущего)
    GROUP BY e1.employee_id
),
-- 2. Максимальная зарплата по отделу
dept_max AS (
    SELECT department_id, MAX(salary) AS max_salary
    FROM employees
    GROUP BY department_id
),
-- 3. Ранжирование по зарплате внутри отдела (топ-N без оконных функций)
emp_rank AS (
    SELECT
        e.employee_id,
        e.first_name,
        e.last_name,
        e.department_id,
        e.salary,
        e.hire_date,
        d.department_name,
        dm.max_salary,
        (SELECT COUNT(*)
         FROM employees e2
         WHERE e2.department_id = e.department_id
           AND e2.salary > e.salary) + 1 AS rank_in_dept
    FROM employees e
    JOIN departments d ON e.department_id = d.department_id
    JOIN dept_max dm ON e.department_id = dm.department_id
    WHERE e.hire_date >= ADD_MONTHS(SYSDATE, -:months_back)
)
SELECT
    er.department_name,
    er.employee_id,
    er.last_name,
    er.salary,
    ma.moving_avg_salary,
    er.max_salary - er.salary AS diff_from_max
FROM emp_rank er
LEFT JOIN moving_avg ma ON er.employee_id = ma.employee_id
WHERE er.rank_in_dept <= :top_n
ORDER BY er.department_name, er.rank_in_dept;"""
        ]
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
        panel = QGroupBox("Ввод SQL запроса")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        btn_example = QPushButton("📋 Пример SQL")
        btn_example.clicked.connect(self.load_example)
        buttons.addWidget(btn_example)

        btn_load = QPushButton("📁 Загрузить")
        btn_load.clicked.connect(self.load_from_file)
        buttons.addWidget(btn_load)

        btn_clear = QPushButton("🗑 Очистить")
        btn_clear.clicked.connect(self.clear_all)
        buttons.addWidget(btn_clear)
        
        buttons.addStretch()
        
        self.highlight_checkbox = QCheckBox("Подсветка синтаксиса")
        self.highlight_checkbox.setChecked(True)
        self.highlight_checkbox.stateChanged.connect(self.toggle_highlighting)
        buttons.addWidget(self.highlight_checkbox)
        
        layout.addLayout(buttons)

        self.sql_input = QTextEdit()
        self.sql_input.setFont(QFont("Courier New", 10))
        self.sql_input.setPlaceholderText("Вставьте SQL здесь...")
        # Подсветка синтаксиса SQL
        self.highlighter = SQLHighlighter(self.sql_input.document())
        layout.addWidget(self.sql_input)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Диалект:"))
        self.dialect_combo = QComboBox()
        self.dialect_combo.addItem("Oracle", SQLDialect.ORACLE)
        self.dialect_combo.addItem("PostgreSQL", SQLDialect.POSTGRESQL)
        self.dialect_combo.addItem("MySQL", SQLDialect.MYSQL)
        self.dialect_combo.addItem("SQL Server", SQLDialect.SQLSERVER)
        self.dialect_combo.addItem("Snowflake", SQLDialect.SNOWFLAKE)
        self.dialect_combo.currentIndexChanged.connect(lambda _: self._set_dialect())
        bottom.addWidget(self.dialect_combo)
        bottom.addStretch()

        parse_btn = QPushButton("📊 Анализировать SQL")
        parse_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        parse_btn.clicked.connect(self.parse_sql)
        bottom.addWidget(parse_btn)
        layout.addLayout(bottom)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QGroupBox("Результаты парсинга")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Общий фильтр:"))
        self.global_filter = QLineEdit()
        self.global_filter.setPlaceholderText("Введите текст для фильтрации всех вкладок...")
        self.global_filter.textChanged.connect(self.apply_global_filter)
        filter_layout.addWidget(self.global_filter)
        clear_filter_btn = QPushButton("Очистить")
        clear_filter_btn.clicked.connect(lambda: self.global_filter.clear())
        filter_layout.addWidget(clear_filter_btn)
        layout.addLayout(filter_layout)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._columns_tab(), "Колонки")
        self.tabs.addTab(self._tables_tab(), "Таблицы")
        self.tabs.addTab(self._lineage_tab(), "Линедж")
        self.tabs.addTab(self._stats_tab(), "Статистика")
        self.tabs.addTab(self._text_output_tab(), "Текстовый вывод")
        layout.addWidget(self.tabs)

        actions = QHBoxLayout()
        copy_btn = QPushButton("📋 Копировать в буфер")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        actions.addWidget(copy_btn)
        actions.addStretch()

        csv_btn = QPushButton("📊 Экспорт CSV")
        csv_btn.clicked.connect(lambda: self.export_data("csv"))
        actions.addWidget(csv_btn)

        excel_btn = QPushButton("📗 Экспорт Excel")
        excel_btn.clicked.connect(lambda: self.export_data("excel"))
        actions.addWidget(excel_btn)

        txt_btn = QPushButton("📝 Экспорт TXT")
        txt_btn.clicked.connect(lambda: self.export_data("text"))
        actions.addWidget(txt_btn)

        json_btn = QPushButton("📤 Экспорт JSON")
        json_btn.clicked.connect(lambda: self.export_data("json"))
        actions.addWidget(json_btn)
        layout.addLayout(actions)
        return panel

    def _tables_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        self.tables_tree = QTreeWidget()
        self.tables_tree.setHeaderLabels(["Схема", "Таблица", "Алиасы", "Тип", "Колонок", "Тип JOIN"])
        self.tables_tree.setSortingEnabled(True)
        self.tables_tree.setColumnWidth(0, 110)
        self.tables_tree.setColumnWidth(1, 190)
        self.tables_tree.setColumnWidth(2, 200)
        self.tables_tree.setColumnWidth(3, 130)
        self.tables_tree.setColumnWidth(4, 80)
        self.tables_tree.setColumnWidth(5, 120)
        self.tables_tree.setColumnWidth(4, 90)
        l.addWidget(self.tables_tree)
        return w

    def _columns_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        self.columns_tree = QTreeWidget()
        self.columns_tree.setHeaderLabels(
            ["Полное имя колонки", "Схема", "Таблица", "Алиас таблицы", "Тип объекта", "Алиасы", "Где используется", "Количество упоминаний"]
        )
        self.columns_tree.setSortingEnabled(True)
        self.columns_tree.setColumnWidth(0, 220)
        self.columns_tree.setColumnWidth(1, 80)
        self.columns_tree.setColumnWidth(2, 120)
        self.columns_tree.setColumnWidth(3, 100)
        self.columns_tree.setColumnWidth(4, 100)  # Тип объекта
        self.columns_tree.setColumnWidth(5, 180)  # Алиасы
        self.columns_tree.setColumnWidth(6, 200)  # Где используется
        self.columns_tree.setColumnWidth(7, 140)  # Количество упоминаний
        l.addWidget(self.columns_tree)
        return w

    def _lineage_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        self.lineage_tree = QTreeWidget()
        self.lineage_tree.setHeaderLabels(["Колонка", "Таблица", "Источник", "Зависимости", "Использование"])
        self.lineage_tree.setSortingEnabled(True)
        self.lineage_tree.setColumnWidth(0, 170)
        self.lineage_tree.setColumnWidth(1, 150)
        self.lineage_tree.setColumnWidth(2, 190)
        self.lineage_tree.setColumnWidth(3, 220)
        self.lineage_tree.setColumnWidth(4, 300)
        l.addWidget(self.lineage_tree)
        return w

    def _stats_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFont(QFont("Arial", 10))
        l.addWidget(self.stats_text)
        return w

    def _text_output_tab(self) -> QWidget:
        """Создание вкладки с текстовым выводом результатов."""
        w = QWidget()
        l = QVBoxLayout(w)
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setFont(QFont("Courier New", 10))
        l.addWidget(self.text_output)
        return w

    def _apply_styles(self) -> None:
        app = QApplication.instance()
        app.setStyleSheet(
            """
            QMainWindow {
                background-color: #f5f7fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #d1d9e6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #2c3e50;
            }
            QTreeWidget {
                background-color: white;
                alternate-background-color: #f8fafc;
                border: 1px solid #e1e8ed;
                border-radius: 4px;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                font-family: "Courier New", monospace;
                font-size: 11px;
                padding: 6px;
            }
            QLineEdit, QComboBox {
                background-color: white;
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3498db;
            }
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                background-color: #f8fafc;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
                border-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #d1e7f8;
            }
            QTabWidget::pane {
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f8fafc;
                border: 1px solid #d1d9e6;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #3498db;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #e8f4fc;
            }
            QStatusBar {
                background-color: #2c3e50;
                color: white;
                font-size: 11px;
            }
            QLabel {
                font-size: 11px;
            }
            QMessageBox {
                background-color: #f5f7fa;
                color: #2c3e50;
            }
            QMessageBox QLabel {
                color: #2c3e50;
            }
            QMessageBox QPushButton {
                background-color: #f8fafc;
                color: #2c3e50;
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QMessageBox QPushButton:hover {
                background-color: #e8f4fc;
                border-color: #3498db;
            }
            """
        )

    def toggle_dark_theme(self, state: int) -> None:
        """Переключает тёмную тему интерфейса.

        Args:
            state: Состояние чекбокса (2 для Qt.CheckState.Checked).
        """
        if state == 2:  # Qt.CheckState.Checked
            app = QApplication.instance()
            app.setStyleSheet(
                """
                QMainWindow {
                    background-color: #2b2b2b;
                }
                QGroupBox {
                    font-weight: bold;
                    font-size: 12px;
                    border: 2px solid #555555;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 12px;
                    background-color: #3c3c3c;
                    color: #e0e0e0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px 0 8px;
                    color: #bbbbbb;
                }
                QTreeWidget {
                    background-color: #3c3c3c;
                    alternate-background-color: #454545;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    font-size: 11px;
                    color: #e0e0e0;
                }
                QTreeWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #555555;
                }
                QTreeWidget::item:selected {
                    background-color: #005a9e;
                    color: white;
                }
                QTextEdit {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    font-family: "Courier New", monospace;
                    font-size: 11px;
                    padding: 6px;
                    color: #e0e0e0;
                }
                QLineEdit, QComboBox {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 11px;
                    color: #e0e0e0;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1px solid #007acc;
                }
                QPushButton {
                    padding: 8px 16px;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    background-color: #555555;
                    font-weight: 500;
                    font-size: 11px;
                    color: #e0e0e0;
                }
                QPushButton:hover {
                    background-color: #666666;
                    border-color: #007acc;
                }
                QPushButton:pressed {
                    background-color: #444444;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                }
                QTabBar::tab {
                    background-color: #555555;
                    border: 1px solid #555555;
                    border-bottom: none;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    color: #e0e0e0;
                }
                QTabBar::tab:selected {
                    background-color: #3c3c3c;
                    border-bottom: 2px solid #007acc;
                    font-weight: bold;
                }
                QTabBar::tab:hover {
                    background-color: #666666;
                }
                QStatusBar {
                    background-color: #1c1c1c;
                    color: #bbbbbb;
                    font-size: 11px;
                }
                QLabel {
                    font-size: 11px;
                    color: #e0e0e0;
                }
                QCheckBox {
                    color: #e0e0e0;
                }
                QMessageBox {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                }
                QMessageBox QLabel {
                    color: #e0e0e0;
                }
                QMessageBox QPushButton {
                    background-color: #555555;
                    color: #e0e0e0;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 11px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #666666;
                    border-color: #007acc;
                }
                """
            )
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
        self.tables_tree.clear()
        self.columns_tree.clear()
        self.lineage_tree.clear()
        self.stats_text.clear()
        if hasattr(self, 'text_output'):
            self.text_output.clear()
        if not self.metadata:
            return

        for col in self.metadata.column_analysis:
            column_row = QTreeWidgetItem(self.columns_tree)
            column_row.setText(0, col.full_name or "")
            # Извлекаем схему, имя таблицы и тип объекта
            table = col.table or ""
            schema = ""
            table_name_without_schema = table
            object_type = ""
            if table:
                if "." in table:
                    parts = table.split(".", 1)
                    schema = parts[0]
                    table_name_without_schema = parts[1]
                # Ищем таблицу в метаданных (сначала по схеме, если нет - по имени)
                found_table = None
                if schema:
                    found_table = self.metadata.get_table_by_name(table_name_without_schema, schema)
                if not found_table:
                    # Поиск по имени без схемы (первая подходящая)
                    for t in self.metadata.get_unique_tables():
                        if t.name == table_name_without_schema:
                            found_table = t
                            break
                if found_table:
                    object_type = found_table.table_type.value
                    # Если схема не была извлечена из table, возьмём из found_table
                    if not schema:
                        schema = found_table.schema or ""
            column_row.setText(1, schema)
            column_row.setText(2, table_name_without_schema)
            column_row.setText(3, col.table_alias or "")
            column_row.setText(4, object_type)  # Тип объекта
            column_row.setText(5, col.get_aliases_str())
            # Фильтруем "calculation" из usage_locations
            filtered_locations = [loc for loc in col.usage_locations if loc.lower() != "calculation"]
            column_row.setText(6, ", ".join(filtered_locations))
            column_row.setText(7, str(col.usage_count))

            lineage_row = QTreeWidgetItem(self.lineage_tree)
            lineage_row.setText(0, col.column_name)
            lineage_row.setText(1, col.table or "")
            lineage_row.setText(2, col.full_name or "")
            lineage_row.setText(3, ", ".join(col.dependencies))
            # Фильтруем "calculation" из usage_locations и не добавляем calculation_type
            filtered_locations = [loc for loc in col.usage_locations if loc.lower() != "calculation"]
            lineage_row.setText(4, ", ".join(filtered_locations))

        for table in self.metadata.get_unique_tables():
            item = QTreeWidgetItem(self.tables_tree)
            item.setText(0, table.schema or "")
            item.setText(1, table.name)
            item.setText(2, table.get_aliases_str())
            item.setText(3, table.table_type.value)
            item.setText(4, str(len(table.columns)))
            item.setText(5, table.join_type or "")

        stats = self.metadata.get_statistics()
        lines = [
            "SQL Metadata Parser v4.0",
            "",
            f"Всего колонок: {stats.get('total_columns', 0)}",
            f"Всего таблиц: {stats.get('total_tables', 0)}",
            f"Уникальных таблиц: {stats.get('unique_tables', 0)}",
            f"Колонок в вычислениях: {stats.get('calculation_columns', 0)}",
            f"Всего упоминаний колонок: {stats.get('total_column_mentions', 0)}",
            "",
            "Пример вывода таблицы 'Колонки':",
            self.metadata.sample_columns_output,
        ]
        self.stats_text.setPlainText("\n".join(lines))
        
        # Обновляем текстовый вывод
        self._update_text_output()

    def _update_text_output(self) -> None:
        """Обновление текстового вывода результатов."""
        if not self.metadata:
            return
        
        from datetime import datetime
        
        text = f"=== РЕЗУЛЬТАТЫ ПАРСИНГА SQL ===\n"
        text += f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += f"Диалект SQL: {self.current_dialect.value}\n\n"
        
        # Уникальные таблицы
        text += "=== УНИКАЛЬНЫЕ ТАБЛИЦЫ ===\n"
        for i, table in enumerate(self.metadata.get_unique_tables(), 1):
            aliases_info = f" (алиасы: {table.get_aliases_str()})" if table.aliases else ""
            text += f"{i}. {table.schema or ''}.{table.name}{aliases_info} - {table.table_type.value}\n"
        text += f"\nВсего уникальных таблиц: {len(self.metadata.get_unique_tables())}\n\n"
        
        # Детальная информация
        text += "=== ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ===\n\n"
        for i, col in enumerate(self.metadata.column_analysis, 1):
            text += f"{i}. Колонка: {col.column_name}\n"
            text += f"   Таблица: {col.table or ''} "
            text += f"(Алиас: {col.table_alias or ''})\n"
            text += f"   Полное имя: {col.full_name or ''}\n"
            text += f"   Вычисление: {col.calculation_type or 'нет'}\n"
            # Фильтруем "calculation" из usage_locations
            filtered_locations = [loc for loc in col.usage_locations if loc.lower() != "calculation"]
            text += f"   Использование: {', '.join(filtered_locations) if filtered_locations else 'нет'}\n"
            text += f"{'-'*40}\n"
        
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
        
        # Определяем фильтры для файлового диалога
        filters = {
            "csv": "CSV файлы (*.csv);;Все файлы (*.*)",
            "excel": "Excel файлы (*.xlsx);;Excel 97-2003 (*.xls);;Все файлы (*.*)",
            "text": "Текстовые файлы (*.txt);;Все файлы (*.*)",
            "json": "JSON файлы (*.json);;Все файлы (*.*)"
        }
        
        file_filter = filters.get(fmt, "Все файлы (*.*)")
        
        # Определяем расширение файла по умолчанию
        default_extensions = {
            "csv": "csv",
            "excel": "xlsx",
            "text": "txt",
            "json": "json"
        }
        default_ext = default_extensions.get(fmt, fmt)
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Экспорт в {fmt.upper()}",
            f"sql_metadata_export.{default_ext}",
            file_filter
        )
        
        if not path:
            return
        
        try:
            ok = self.export_manager.export(self.metadata, path, strategy_name=fmt)
            if ok:
                self.status_bar.showMessage(f"Данные экспортированы в {fmt.upper()}: {os.path.basename(path)}")
                
                # Предложить открыть файл
                reply = QMessageBox.question(
                    self,
                    "Успех",
                    f"Файл успешно создан!\n\n"
                    f"Всего строк: {len(self.metadata.column_analysis)}\n"
                    f"Уникальных таблиц: {len(self.metadata.get_unique_tables())}\n\n"
                    f"Открыть файл сейчас?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(path)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось экспортировать данные")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать данные:\n{str(e)}")

    def copy_to_clipboard(self) -> None:
        """Копирует сводку колонок в буфер обмена в формате TSV."""
        if not self.metadata:
            return
        rows = ["Полное имя\tАлиасы\tТаблица\tГде используется\tКоличество упоминаний"]
        for col in self.metadata.column_analysis:
            rows.append(
                f"{col.full_name}\t{col.get_aliases_str()}\t{col.table or ''}\t"
                f"{', '.join(col.usage_locations)}\t{col.usage_count}"
            )
        QApplication.clipboard().setText("\n".join(rows))
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
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Справка")
        msg_box.setText(HELP_TEXT)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        # Применяем стиль в зависимости от темы
        if self.dark_theme_checkbox.isChecked():
            # Стиль для тёмной темы
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                }
                QMessageBox QLabel {
                    color: #e0e0e0;
                }
                QMessageBox QPushButton {
                    background-color: #555555;
                    color: #e0e0e0;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 11px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #666666;
                    border-color: #007acc;
                }
            """)
        else:
            # Стиль для светлой темы
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f5f7fa;
                    color: #2c3e50;
                }
                QMessageBox QLabel {
                    color: #2c3e50;
                }
                QMessageBox QPushButton {
                    background-color: #f8fafc;
                    color: #2c3e50;
                    border: 1px solid #d1d9e6;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 11px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #e8f4fc;
                    border-color: #3498db;
                }
            """)
        
        msg_box.exec()
