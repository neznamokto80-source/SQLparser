"""
Data models for SQL parser metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class TableType(Enum):
    """Типы таблиц, которые могут быть обнаружены в SQL запросе."""
    TABLE = "Таблица"
    SUBQUERY = "Подзапрос"
    CTE = "CTE"
    VIEW = "Представление"
    UNKNOWN = "Неизвестно"


@dataclass
class ColumnMetadata:
    """Метаданные колонки SQL запроса.

    Attributes:
        column_name: Имя колонки (например, "user_id").
        table: Имя таблицы (например, "users").
        table_alias: Алиас таблицы (например, "u").
        full_name: Полное имя колонки (например, "users.user_id").
        aliases: Список алиасов колонки (например, ["uid", "id"]).
        column_aliases: Список алиасов колонки в SELECT (например, ["user_id AS uid"]).
        usage_locations: Места использования колонки (например, ["SELECT", "WHERE"]).
        usage_count: Количество упоминаний колонки в запросе.
        is_calculation: Является ли колонка вычисляемой (например, "COUNT(*)").
        calculation_type: Тип вычисления (например, "aggregate", "function").
        calculation_expression: Выражение вычисления (например, "COUNT(*)").
        dependencies: Зависимости колонки (например, ["users.id"]).
    """
    column_name: str
    table: Optional[str] = None
    table_alias: Optional[str] = None
    full_name: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    column_aliases: List[str] = field(default_factory=list)
    usage_locations: List[str] = field(default_factory=list)
    usage_count: int = 0
    is_calculation: bool = False
    calculation_type: Optional[str] = None
    calculation_expression: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Возвращает имя колонки (синоним column_name)."""
        return self.column_name

    @property
    def table_name(self) -> Optional[str]:
        """Возвращает имя таблицы (синоним table)."""
        return self.table

    def normalize(self) -> None:
        """Нормализует поля: вычисляет full_name, сортирует и удаляет дубликаты."""
        if not self.full_name:
            self.full_name = f"{self.table}.{self.column_name}" if self.table else self.column_name
        self.aliases = sorted(set(filter(None, self.aliases)))
        self.column_aliases = sorted(set(filter(None, self.column_aliases)))
        self.usage_locations = sorted(set(filter(None, self.usage_locations)))
        self.dependencies = sorted(set(filter(None, self.dependencies)))

    def get_aliases_str(self) -> str:
        """Возвращает строку с алиасами колонки, разделёнными запятой.

        Returns:
            Строка вида "alias1, alias2".
        """
        self.normalize()
        return ", ".join(self.aliases)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь для сериализации.

        Returns:
            Словарь со всеми полями колонки.
        """
        self.normalize()
        return {
            "full_name": self.full_name,
            "table": self.table,
            "table_alias": self.table_alias,
            "column_name": self.column_name,
            "aliases": self.aliases,
            "column_aliases": self.column_aliases,
            "usage_locations": self.usage_locations,
            "usage_count": self.usage_count,
            "is_calculation": self.is_calculation,
            "calculation_type": self.calculation_type,
            "calculation_expression": self.calculation_expression,
            "dependencies": self.dependencies,
        }


@dataclass
class TableInfo:
    """Метаданные таблицы SQL запроса.

    Attributes:
        name: Имя таблицы (например, "users").
        schema: Схема таблицы (например, "public").
        aliases: Множество алиасов таблицы (например, {"u", "usr"}).
        table_type: Тип таблицы (см. TableType).
        columns: Множество полных имён колонок, принадлежащих таблице.
    """
    name: str
    schema: Optional[str] = None
    aliases: Set[str] = field(default_factory=set)
    table_type: TableType = TableType.TABLE
    columns: Set[str] = field(default_factory=set)

    def add_alias(self, alias: Optional[str]) -> None:
        """Добавляет алиас таблицы.

        Args:
            alias: Алиас таблицы (например, "u").
        """
        if alias:
            self.aliases.add(alias)

    def add_column(self, full_name: str) -> None:
        """Добавляет колонку в таблицу.

        Args:
            full_name: Полное имя колонки (например, "users.user_id").
        """
        if full_name:
            self.columns.add(full_name)

    def get_aliases_str(self) -> str:
        """Возвращает строку с алиасами таблицы, разделёнными запятой.

        Returns:
            Строка вида "alias1, alias2".
        """
        return ", ".join(sorted(self.aliases))

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь для сериализации.

        Returns:
            Словарь с полями таблицы.
        """
        return {
            "name": self.name,
            "schema": self.schema,
            "aliases": sorted(self.aliases),
            "type": self.table_type.value,
            "column_count": len(self.columns),
        }


@dataclass
class SQLMetadata:
    """Основной контейнер метаданных, полученных при парсинге SQL запроса.

    Attributes:
        columns: Список метаданных колонок.
        tables: Список метаданных таблиц.
        original_sql: Исходный SQL запрос.
        parse_errors: Список ошибок парсинга.
        json_schema: JSON схема метаданных (для совместимости).
        sample_columns_output: Пример текстового вывода колонок.
    """
    columns: List[ColumnMetadata] = field(default_factory=list)
    tables: List[TableInfo] = field(default_factory=list)
    original_sql: str = ""
    parse_errors: List[str] = field(default_factory=list)
    json_schema: Dict[str, Any] = field(default_factory=dict)
    sample_columns_output: str = ""

    def add_column(self, column: ColumnMetadata) -> None:
        """Добавляет колонку в метаданные.

        Args:
            column: Объект ColumnMetadata.
        """
        column.normalize()
        self.columns.append(column)

    def add_table(self, table: TableInfo) -> None:
        """Добавляет таблицу в метаданные.

        Args:
            table: Объект TableInfo.
        """
        self.tables.append(table)

    def get_unique_tables(self) -> List[TableInfo]:
        """Возвращает список уникальных таблиц, объединяя дубликаты по схеме, имени и типу.

        Returns:
            Список TableInfo с объединёнными алиасами и колонками.
        """
        unique: Dict[tuple, TableInfo] = {}
        for table in self.tables:
            key = (table.schema, table.name, table.table_type)
            if key not in unique:
                unique[key] = table
            else:
                unique[key].aliases.update(table.aliases)
                unique[key].columns.update(table.columns)
        return list(unique.values())

    def get_table_by_name(self, name: str, schema: Optional[str] = None) -> Optional[TableInfo]:
        """Находит таблицу по имени и схеме.

        Args:
            name: Имя таблицы.
            schema: Опциональная схема таблицы.

        Returns:
            TableInfo или None, если таблица не найдена.
        """
        for table in self.get_unique_tables():
            if table.name == name and table.schema == schema:
                return table
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Вычисляет статистику по метаданным.

        Returns:
            Словарь с ключами:
                - total_columns: общее количество колонок
                - total_tables: общее количество таблиц
                - unique_tables: количество уникальных таблиц
                - calculation_columns: количество вычисляемых колонок
                - total_column_mentions: общее количество упоминаний колонок
                - table_types: распределение типов таблиц
        """
        type_counts: Dict[str, int] = {}
        for table in self.tables:
            label = table.table_type.value
            type_counts[label] = type_counts.get(label, 0) + 1

        calculation_columns = sum(1 for col in self.columns if col.is_calculation)
        total_mentions = sum(col.usage_count for col in self.columns)
        return {
            "total_columns": len(self.columns),
            "total_tables": len(self.tables),
            "unique_tables": len(self.get_unique_tables()),
            "calculation_columns": calculation_columns,
            "total_column_mentions": total_mentions,
            "table_types": type_counts,
        }

    @property
    def column_analysis(self) -> List[ColumnMetadata]:
        """Синоним для columns (обратная совместимость)."""
        return self.columns
