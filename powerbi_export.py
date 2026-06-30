#!/usr/bin/env python3
"""
powerbi_export.py — Автономный скрипт для парсинга SQL-запросов из Oracle БД
и записи результатов в таблицу для загрузки в Power BI.

Особенности:
- Чтение SQL из SAP_BO_DATAPROVIDERS (поле SQL_TEXT типа CLOB)
- Нормализация SQL: двойные пробелы -> перенос строки
- Автоопределение диалекта: Oracle -> TSQL -> PostgreSQL
- Запись результатов в SAP_BO_SQL_PARSE_RESULTS
- Составной ключ KEY = REP_ID + '_' + DP_ID (без дублирования SQL_TEXT)
"""

from __future__ import annotations

import os
import sys
import re
import json
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
from dotenv import load_dotenv

# cx_Oracle импортируем опционально (требует Oracle Instant Client)
try:
    import cx_Oracle
    HAS_ORACLE = True
except ImportError:
    cx_Oracle = None
    HAS_ORACLE = False

# =============================================================================
# 1. ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# =============================================================================

script_dir = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(script_dir, 'prod_env.env')

def load_config() -> dict:
    """Загружает конфигурацию из .env файла."""
    if not os.path.exists(ENV_FILE):
        print(f"Файл .env не найден: {ENV_FILE}")
        sys.exit(1)

    load_dotenv(ENV_FILE)

    def get_env(var_name: str, required: bool = True, default: str = '') -> str:
        value = os.getenv(var_name)
        if not value and required:
            print(f"Ошибка: переменная {var_name} не задана в .env")
            sys.exit(1)
        return value or default

    return {
        'db_user': get_env('DB_USER'),
        'db_pass': get_env('DB_PASS'),
        'db_dsn': get_env('DB_DSN'),
        'providers_table': get_env('PROVIDERS_TABLE', required=False, default='SAP_BO_DATAPROVIDERS'),
        'results_table': get_env('RESULTS_TABLE', required=False, default='SAP_BO_SQL_PARSE_RESULTS'),
    }

# =============================================================================
# 2. МОДЕЛИ ДАННЫХ
# =============================================================================

class TableType(Enum):
    """Типы таблиц, которые могут быть обнаружены в SQL запросе."""
    TABLE = "Таблица"
    SUBQUERY = "Подзапрос"
    CTE = "CTE"
    VIEW = "Представление"
    UNKNOWN = "Неизвестно"


@dataclass
class ColumnMetadata:
    """Метаданные колонки SQL запроса."""
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
        return self.column_name

    @property
    def table_name(self) -> Optional[str]:
        return self.table

    def normalize(self) -> None:
        if not self.full_name:
            self.full_name = f"{self.table}.{self.column_name}" if self.table else self.column_name
        self.aliases = sorted(set(filter(None, self.aliases)))
        self.column_aliases = sorted(set(filter(None, self.column_aliases)))
        self.usage_locations = sorted(set(filter(None, self.usage_locations)))
        self.dependencies = sorted(set(filter(None, self.dependencies)))

    def to_dict(self) -> Dict[str, Any]:
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
    """Метаданные таблицы SQL запроса."""
    name: str
    schema: Optional[str] = None
    aliases: Set[str] = field(default_factory=set)
    table_type: TableType = TableType.TABLE
    columns: Set[str] = field(default_factory=set)
    join_type: Optional[str] = None

    def add_alias(self, alias: Optional[str]) -> None:
        if alias:
            self.aliases.add(alias)

    def add_column(self, full_name: str) -> None:
        if full_name:
            self.columns.add(full_name)

    def get_aliases_str(self) -> str:
        return ", ".join(sorted(self.aliases))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema": self.schema,
            "aliases": sorted(self.aliases),
            "type": self.table_type.value,
            "column_count": len(self.columns),
            "join_type": self.join_type,
        }


@dataclass
class SQLMetadata:
    """Основной контейнер метаданных, полученных при парсинге SQL запроса."""
    columns: List[ColumnMetadata] = field(default_factory=list)
    tables: List[TableInfo] = field(default_factory=list)
    original_sql: str = ""
    parse_errors: List[str] = field(default_factory=list)
    json_schema: Dict[str, Any] = field(default_factory=dict)
    sample_columns_output: str = ""

    def add_column(self, column: ColumnMetadata) -> None:
        column.normalize()
        self.columns.append(column)

    def add_table(self, table: TableInfo) -> None:
        self.tables.append(table)

    def get_unique_tables(self) -> List[TableInfo]:
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
        for table in self.get_unique_tables():
            if table.name == name and table.schema == schema:
                return table
        return None

    def get_statistics(self) -> Dict[str, Any]:
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
        return self.columns


# =============================================================================
# 3. SQL DIALECT
# =============================================================================

class SQLDialect(Enum):
    """Поддерживаемые SQL диалекты."""
    ORACLE = "oracle"
    POSTGRESQL = "postgres"
    MYSQL = "mysql"
    SQLSERVER = "tsql"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    SQLITE = "sqlite"
    CLICKHOUSE = "clickhouse"
    REDSHIFT = "redshift"
    DATABRICKS = "databricks"
    HIVE = "hive"
    PRESTO = "presto"
    TRINO = "trino"
    DUCKDB = "duckdb"
    TERADATA = "teradata"


def dialect_to_sqlglot(dialect: SQLDialect) -> str:
    """Преобразует внутренний enum диалекта в строку для sqlglot."""
    mapping = {
        SQLDialect.ORACLE: "oracle",
        SQLDialect.POSTGRESQL: "postgres",
        SQLDialect.MYSQL: "mysql",
        SQLDialect.SQLSERVER: "tsql",
        SQLDialect.SNOWFLAKE: "snowflake",
        SQLDialect.BIGQUERY: "bigquery",
        SQLDialect.SQLITE: "sqlite",
        SQLDialect.CLICKHOUSE: "clickhouse",
        SQLDialect.REDSHIFT: "redshift",
        SQLDialect.DATABRICKS: "databricks",
        SQLDialect.HIVE: "hive",
        SQLDialect.PRESTO: "presto",
        SQLDialect.TRINO: "trino",
        SQLDialect.DUCKDB: "duckdb",
        SQLDialect.TERADATA: "teradata",
    }
    return mapping.get(dialect, "oracle")


# =============================================================================
# 4. SQL ПРЕПРОЦЕССОР
# =============================================================================

class SQLPreprocessor:
    """Препроцессор для очистки SQL запросов перед парсингом."""

    def __init__(self, dialect: SQLDialect = SQLDialect.ORACLE):
        self.dialect = dialect

    def preprocess(self, sql: str) -> str:
        if not sql:
            return sql
        sql = self._remove_comments(sql)
        sql = self._replace_convert_functions(sql)
        sql = self._replace_to_date_functions(sql)
        sql = self._replace_variable_functions(sql)
        sql = self._handle_star_operator(sql)
        sql = self._remove_square_brackets(sql)
        sql = self._fix_common_issues(sql)
        return sql

    def _remove_comments(self, sql: str) -> str:
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        return sql.strip()

    def _apply_patterns(self, sql: str, patterns: list) -> str:
        result = sql
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _replace_convert_functions(self, sql: str) -> str:
        patterns = [
            (r"\bCONVERT\s*\(\s*datetime\s*,\s*([^,)]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS datetime)"),
            (r"\bCONVERT\s*\(\s*date\s*,\s*([^,)]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS date)"),
            (r"\bCONVERT\s*\(\s*smalldatetime\s*,\s*([^,)]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS smalldatetime)"),
            (r"\bCONVERT\s*\(\s*datetime2\s*,\s*([^,)]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS datetime2)"),
            (r"\bCONVERT\s*\(\s*(numeric|decimal)\s*\(\s*\d+\s*,\s*\d+\s*\)\s*,\s*([^,)]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\2 AS \1)"),
            (r"\bCONVERT\s*\(\s*(var)?char\s*\(\s*\d+\s*\)\s*,\s*([^,)]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\2 AS \1char)"),
            (r"\bCONVERT\s*\(\s*(\w+)\s*,\s*([^,)]+)\s*\)", r"CAST(\2 AS \1)"),
        ]
        return self._apply_patterns(sql, patterns)

    def _replace_to_date_functions(self, sql: str) -> str:
        patterns = [
            (r"\bto_date\s*\(\s*@\w+\([^)]*\)\s*,\s*'([^']+)'\s*\)", r"CAST('2000-01-01' AS DATE)"),
            (r"\bto_date\s*\(\s*([^,]+)\s*,\s*'([^']+)'\s*\)", r"CAST('2000-01-01' AS DATE)"),
            (r"\bto_date\s*\(\s*([^)]+)\s*\)", r"CAST('2000-01-01' AS DATE)"),
        ]
        return self._apply_patterns(sql, patterns)

    def _replace_variable_functions(self, sql: str) -> str:
        pattern = r"@\w+\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
        return re.sub(pattern, "''", sql)

    def _handle_star_operator(self, sql: str) -> str:
        sql = re.sub(r"(\bSELECT\b)(\s+)\*", r"\1 _star_", sql, flags=re.IGNORECASE)
        sql = sql.replace(".*", "._star_")
        sql = re.sub(r",\s*\*\s*,", ",_star_,", sql)
        sql = re.sub(r"\*\s+(\bFROM\b)", r"_star_ \1", sql, flags=re.IGNORECASE)
        return sql

    def _remove_square_brackets(self, sql: str) -> str:
        """Заменяет квадратные скобки на кавычки в зависимости от диалекта."""
        state = 0
        result = []
        i = 0
        while i < len(sql):
            ch = sql[i]
            if ch == "'" and state == 0:
                state = 1
                result.append(ch)
            elif ch == "'" and state == 1:
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    result.append(ch)
                    i += 1
                    result.append(sql[i])
                else:
                    state = 0
                    result.append(ch)
            elif ch == '"' and state == 0:
                state = 2
                result.append(ch)
            elif ch == '"' and state == 2:
                if i + 1 < len(sql) and sql[i + 1] == '"':
                    result.append(ch)
                    i += 1
                    result.append(sql[i])
                else:
                    state = 0
                    result.append(ch)
            elif ch == '[' and state == 0:
                j = i + 1
                while j < len(sql) and sql[j] != ']':
                    j += 1
                if j < len(sql):
                    identifier = sql[i+1:j]
                    if self.dialect == SQLDialect.SQLSERVER:
                        result.append(f'[{identifier}]')
                    elif self.dialect == SQLDialect.MYSQL:
                        result.append(f'`{identifier}`')
                    else:
                        result.append(f'"{identifier}"')
                    i = j
                else:
                    result.append(ch)
            elif ch == ']' and state == 0:
                result.append(ch)
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    def _fix_common_issues(self, sql: str) -> str:
        sql = re.sub(r"\s+", " ", sql)
        sql = sql.replace(", ,", ",")
        sql = sql.replace(",.", ",")
        sql = re.sub(r'^"', "", sql)
        sql = re.sub(r'\s+\)', ')', sql)
        return sql.strip()

    def validate_sql(self, sql: str) -> tuple[bool, Optional[str]]:
        if not sql:
            return False, "SQL запрос не может быть пустым"
        sql_upper = sql.upper()
        if "SELECT" not in sql_upper:
            return False, "SQL запрос должен содержать ключевое слово SELECT"
        if "FROM" not in sql_upper and "WHERE" in sql_upper:
            return False, "SQL запрос с WHERE должен содержать FROM"
        return True, None


# =============================================================================
# 5. ПАРСЕР SQL (sqlglot)
# =============================================================================

try:
    from sqlglot import exp, parse_one
except ImportError:
    print("Ошибка: библиотека sqlglot не установлена. Установите: pip install sqlglot")
    sys.exit(1)


CALCULATION_NODES = (
    exp.AggFunc,
    exp.Anonymous,
    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
    exp.Mod,
    exp.Case,
    exp.Cast,
    exp.Window,
)


@dataclass
class ScopeInfo:
    alias_to_table: Dict[str, str]
    tables: Set[str]


class DetailedColumnAnalyzer:
    """Детальный анализатор колонок, алиасов и контекстов использования."""

    def __init__(self, ast: exp.Expression, original_sql: Optional[str] = None):
        self.ast = ast
        self.original_sql = original_sql
        self.columns: Dict[str, ColumnMetadata] = {}
        self.tables: Dict[Tuple[Optional[str], str, TableType], TableInfo] = {}
        self.column_alias_to_source: Dict[str, str] = {}
        self.scope_by_select_id: Dict[int, ScopeInfo] = {}
        self.subquery_column_map: Dict[Tuple[str, str], str] = {}
        self.cte_column_map: Dict[Tuple[str, str], str] = {}
        self.source_alias_hints: Dict[str, Set[str]] = {}
        self.select_aliases: Set[str] = set()

    def _detect_oracle_outer_join(self) -> Dict[str, str]:
        if not self.original_sql:
            return {}
        sql = self.original_sql.upper()
        pattern = r'([A-Z0-9_]+(?:\.[A-Z0-9_]+)?)\s*\(\+\)'
        matches = re.findall(pattern, sql)
        result = {}
        for column_spec in matches:
            if '.' in column_spec:
                table = column_spec.split('.')[0]
            else:
                continue
            result[table] = "LEFT JOIN"
        return result

    def analyze(self) -> Tuple[List[ColumnMetadata], List[TableInfo], str]:
        self._collect_tables()
        self._collect_scopes()
        self._collect_subquery_and_cte_column_maps()
        self._scan_nodes_once()
        self._process_join_using()
        self._apply_source_alias_hints()
        columns = list(self.columns.values())
        for column in columns:
            column.normalize()
        return columns, list(self.tables.values()), self._render_columns_sample(columns)

    def _collect_tables(self) -> None:
        oracle_join_types = self._detect_oracle_outer_join()
        for cte in self.ast.find_all(exp.CTE):
            cte_name = cte.alias_or_name
            if cte_name:
                self._upsert_table(cte_name, None, cte_name, TableType.CTE)
        for table in self.ast.find_all(exp.Table):
            name = table.name
            schema = table.db
            alias = table.alias_or_name if table.alias else None
            table_type = TableType.CTE if self._is_cte_table(name) else TableType.TABLE
            join_type = self._get_join_type_for_table(table)
            if join_type is None or join_type == "INNER JOIN":
                if alias and alias.upper() in oracle_join_types:
                    join_type = oracle_join_types[alias.upper()]
                elif name.upper() in oracle_join_types:
                    join_type = oracle_join_types[name.upper()]
            self._upsert_table(name, schema, alias, table_type, join_type)
        for subquery in self.ast.find_all(exp.Subquery):
            alias = subquery.alias_or_name
            if alias:
                self._upsert_table(alias, None, alias, TableType.SUBQUERY)

    def _collect_scopes(self) -> None:
        for select in self.ast.find_all(exp.Select):
            alias_to_table: Dict[str, str] = {}
            tables: Set[str] = set()
            from_node = select.args.get("from_")
            if from_node:
                for table in from_node.find_all(exp.Table):
                    name = table.name
                    alias = table.alias_or_name if table.alias else None
                    tables.add(name)
                    if alias:
                        alias_to_table[alias] = name
            joins = select.args.get("joins") or []
            for join in joins:
                for table in join.find_all(exp.Table):
                    name = table.name
                    alias = table.alias_or_name if table.alias else None
                    tables.add(name)
                    if alias:
                        alias_to_table[alias] = name
            self.scope_by_select_id[id(select)] = ScopeInfo(alias_to_table=alias_to_table, tables=tables)

    def _scan_nodes_once(self) -> None:
        for node in self.ast.walk():
            if isinstance(node, exp.Alias):
                self._process_alias(node)
                continue
            if isinstance(node, exp.Column):
                self._process_column(node)

    def _process_alias(self, alias_node: exp.Alias) -> None:
        alias_name = alias_node.alias_or_name
        if not alias_name:
            return
        self.select_aliases.add(alias_name)
        source_columns = list(alias_node.this.find_all(exp.Column))
        alias_is_calculation = self._expression_is_calculation(alias_node.this)
        if alias_is_calculation:
            calc_key = f"CALC.{alias_name}"
            if calc_key not in self.columns:
                meta = ColumnMetadata(
                    column_name=alias_name,
                    table=None,
                    table_alias=None,
                    full_name=alias_name,
                    aliases=[alias_name],
                    is_calculation=True,
                    calculation_type=self._calculation_type(alias_node.this),
                    calculation_expression=alias_node.this.sql(),
                )
                meta.usage_count = 1
                meta.usage_locations.append("SELECT")
                self.columns[calc_key] = meta
            else:
                meta = self.columns[calc_key]
                meta.usage_count += 1
                if "SELECT" not in meta.usage_locations:
                    meta.usage_locations.append("SELECT")
            for src in source_columns:
                source_key, _ = self._resolve_column_key(src)
                if source_key and source_key not in meta.dependencies:
                    meta.dependencies.append(source_key)
            self.column_alias_to_source[alias_name] = calc_key
        else:
            for src in source_columns:
                source_key, source_table_alias = self._resolve_column_key(src)
                if not source_key:
                    continue
                meta = self._get_or_create_column(source_key, source_table_alias)
                if alias_name not in meta.column_aliases:
                    meta.column_aliases.append(alias_name)
                if alias_name not in meta.aliases:
                    meta.aliases.append(alias_name)
                self.column_alias_to_source.setdefault(alias_name, source_key)
                calc, calc_parent = self._is_calculation_column(src)
                if calc:
                    meta.is_calculation = True
                    meta.calculation_type = self._calculation_type(calc_parent)
                    meta.calculation_expression = calc_parent.sql() if calc_parent else alias_node.this.sql()

    def _process_column(self, column_node: exp.Column) -> None:
        key, table_alias = self._resolve_column_key(column_node)
        if not key:
            return
        meta = self._get_or_create_column(key, table_alias)
        if table_alias and table_alias != meta.table:
            alias_ref = f"{table_alias}.{meta.column_name}"
            if alias_ref not in meta.aliases:
                meta.aliases.append(alias_ref)
        for context in self._detect_usage_context(column_node):
            meta.usage_locations.append(context)
        calc, calc_parent = self._is_calculation_column(column_node)
        if calc:
            meta.is_calculation = True
            meta.calculation_type = self._calculation_type(calc_parent)
            meta.calculation_expression = calc_parent.sql() if calc_parent else column_node.sql()
        meta.usage_count += 1
        if table_alias and self._is_cte_table(table_alias):
            col_name = column_node.name
            if col_name and col_name != "_star_":
                cte_key = f"{table_alias}.{col_name}"
                cte_meta = self.columns.get(cte_key)
                if cte_meta and cte_meta is not meta:
                    cte_meta.usage_count += 1
                    for context in self._detect_usage_context(column_node):
                        if context not in cte_meta.usage_locations:
                            cte_meta.usage_locations.append(context)

    def _process_join_using(self) -> None:
        for join in self.ast.find_all(exp.Join):
            using_args = join.args.get("using")
            if not using_args:
                continue
            names: List[str] = []
            for expr_item in using_args:
                if isinstance(expr_item, exp.Identifier):
                    names.append(expr_item.name)
                elif hasattr(expr_item, "name"):
                    names.append(expr_item.name)
            if not names:
                continue
            select_scope = self._nearest_select_scope(join)
            if not select_scope:
                continue
            candidate_tables = sorted(select_scope.tables)
            for col_name in names:
                for table_name in candidate_tables:
                    key = f"{table_name}.{col_name}"
                    meta = self._get_or_create_column(key, None)
                    meta.usage_locations.append("JOIN")

    def _resolve_column_key(self, column_node: exp.Column) -> Tuple[Optional[str], Optional[str]]:
        table_ref = column_node.table
        col_name = column_node.name
        if col_name == "_star_":
            col_name = "*"
        if not col_name:
            return None, None
        if not table_ref and col_name in self.column_alias_to_source:
            return self.column_alias_to_source[col_name], None
        if not table_ref and col_name in self.select_aliases:
            return None, None
        if table_ref:
            mapped_key = self.subquery_column_map.get((table_ref, col_name))
            if mapped_key:
                return mapped_key, table_ref
            mapped_key = self.cte_column_map.get((table_ref, col_name))
            if mapped_key:
                return mapped_key, table_ref
            scope = self._nearest_select_scope(column_node)
            table_name = None
            if scope and table_ref in scope.alias_to_table:
                table_name = scope.alias_to_table[table_ref]
            else:
                table_name = table_ref
            return f"{table_name}.{col_name}", table_ref
        scope = self._nearest_select_scope(column_node)
        if scope and len(scope.tables) == 1:
            table_name = next(iter(scope.tables))
            return f"{table_name}.{col_name}", None
        return f"UNKNOWN.{col_name}", None

    def _get_or_create_column(self, key: str, table_alias: Optional[str]) -> ColumnMetadata:
        if key in self.columns:
            meta = self.columns[key]
            if table_alias and not meta.table_alias:
                meta.table_alias = table_alias
            elif table_alias and meta.table_alias:
                current_is_cte = self._is_cte_table(meta.table_alias)
                new_is_cte = self._is_cte_table(table_alias)
                if current_is_cte and not new_is_cte:
                    meta.table_alias = table_alias
            return meta
        table_name, col_name = key.split(".", 1)
        meta = ColumnMetadata(
            column_name=col_name,
            table=None if table_name == "UNKNOWN" else table_name,
            table_alias=table_alias,
            full_name=key if table_name != "UNKNOWN" else col_name,
            aliases=[],
        )
        if table_alias:
            meta.aliases.append(f"{table_alias}.{meta.column_name}")
        if meta.table:
            table_obj = self._find_table_by_name(meta.table)
            if table_obj:
                table_obj.add_column(meta.full_name or key)
        self.columns[key] = meta
        return meta

    def _collect_subquery_and_cte_column_maps(self) -> None:
        for subquery in self.ast.find_all(exp.Subquery):
            sub_alias = subquery.alias_or_name
            if not sub_alias or not isinstance(subquery.this, exp.Select):
                continue
            self._collect_projection_map(sub_alias, subquery.this, self.subquery_column_map)
        for cte in self.ast.find_all(exp.CTE):
            cte_name = cte.alias_or_name
            if not cte_name or not isinstance(cte.this, exp.Select):
                continue
            self._collect_projection_map(cte_name, cte.this, self.cte_column_map)

    def _collect_projection_map(
        self,
        relation_alias: str,
        select_node: exp.Select,
        target_map: Dict[Tuple[str, str], str],
    ) -> None:
        for expression in select_node.args.get("expressions") or []:
            output_name = expression.alias_or_name
            if not output_name and isinstance(expression, exp.Column):
                output_name = expression.name
            if not output_name:
                continue
            source_column = next(expression.find_all(exp.Column), None)
            if not source_column:
                continue
            source_key, _ = self._resolve_column_key(source_column)
            if source_key:
                target_map[(relation_alias, output_name)] = source_key
                alias_hint = f"{relation_alias}.{output_name}"
                if source_key not in self.source_alias_hints:
                    self.source_alias_hints[source_key] = set()
                self.source_alias_hints[source_key].add(alias_hint)
                cte_column_key = f"{relation_alias}.{output_name}"
                expr_for_calc = expression.this if isinstance(expression, exp.Alias) else expression
                is_calculation = self._expression_is_calculation(expr_for_calc)
                if cte_column_key in self.columns:
                    meta = self.columns[cte_column_key]
                    if is_calculation:
                        meta.is_calculation = True
                        meta.calculation_type = self._calculation_type(expr_for_calc)
                        meta.calculation_expression = expr_for_calc.sql()
                    meta.usage_count += 1
                    if "SELECT" not in meta.usage_locations:
                        meta.usage_locations.append("SELECT")
                else:
                    meta = ColumnMetadata(
                        column_name=output_name,
                        table=relation_alias,
                        table_alias=relation_alias,
                        full_name=cte_column_key,
                        aliases=[alias_hint],
                        is_calculation=is_calculation,
                        calculation_type=self._calculation_type(expr_for_calc) if is_calculation else None,
                        calculation_expression=expr_for_calc.sql() if is_calculation else None,
                    )
                    meta.usage_count = 1
                    meta.usage_locations.append("SELECT")
                    self.columns[cte_column_key] = meta
                    table_obj = self._find_table_by_name(relation_alias)
                    if table_obj:
                        table_obj.add_column(cte_column_key)
                for col in expr_for_calc.find_all(exp.Column):
                    col_key, _ = self._resolve_column_key(col)
                    if col_key and col_key not in meta.dependencies:
                        meta.dependencies.append(col_key)

    def _apply_source_alias_hints(self) -> None:
        for source_key, hints in self.source_alias_hints.items():
            meta = self.columns.get(source_key)
            if not meta:
                continue
            for hint in sorted(hints):
                if hint not in meta.aliases:
                    meta.aliases.append(hint)
            full_name_alias = meta.full_name or ""
            if full_name_alias and full_name_alias in meta.aliases:
                meta.aliases = [alias for alias in meta.aliases if alias != full_name_alias]

    def _detect_usage_context(self, node: exp.Column) -> List[str]:
        context: Set[str] = set()
        parent = node.parent
        owning_select = self._nearest_select_scope(node)
        while parent:
            if isinstance(parent, exp.Select):
                select_exprs = parent.args.get("expressions") or []
                if node in select_exprs:
                    context.add("SELECT")
            elif isinstance(parent, exp.Where):
                context.add("WHERE")
            elif isinstance(parent, exp.Join):
                context.add("JOIN")
            elif isinstance(parent, exp.Group):
                context.add("GROUP BY")
            elif isinstance(parent, exp.Having):
                context.add("HAVING")
            elif isinstance(parent, exp.Order):
                context.add("ORDER BY")
            elif isinstance(parent, exp.Alias):
                grandparent = parent.parent
                if isinstance(grandparent, exp.Select):
                    select_exprs = grandparent.args.get("expressions") or []
                    if parent in select_exprs:
                        context.add("SELECT")
            if self._expression_is_calculation(parent):
                context.add("calculation")
            if owning_select is not None and parent is owning_select:
                break
            parent = parent.parent
        return sorted(context) if context else ["UNKNOWN"]

    def _is_calculation_column(self, node: exp.Column) -> Tuple[bool, Optional[exp.Expression]]:
        parent = node.parent
        while parent:
            if self._expression_is_calculation(parent):
                return True, parent
            parent = parent.parent
        return False, None

    def _expression_is_calculation(self, expression: exp.Expression) -> bool:
        if isinstance(expression, CALCULATION_NODES):
            return True
        if isinstance(expression, exp.Func):
            if isinstance(expression, (exp.Connector, exp.Predicate)):
                return False
            return True
        return False

    def _calculation_type(self, parent: Optional[exp.Expression]) -> Optional[str]:
        if parent is None:
            return None
        if isinstance(parent, exp.AggFunc):
            return parent.__class__.__name__.upper()
        if isinstance(parent, (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod)):
            return "ARITHMETIC"
        if isinstance(parent, exp.Case):
            return "CASE"
        if isinstance(parent, exp.Cast):
            return "CAST"
        if isinstance(parent, exp.Anonymous):
            return (parent.name or "FUNCTION").upper()
        if isinstance(parent, exp.Func):
            return parent.__class__.__name__.upper()
        return parent.__class__.__name__.upper()

    def _nearest_select_scope(self, node: exp.Expression) -> Optional[ScopeInfo]:
        parent = node
        while parent:
            if isinstance(parent, exp.Select):
                return self.scope_by_select_id.get(id(parent))
            parent = parent.parent
        return None

    def _is_cte_table(self, table_name: str) -> bool:
        for cte in self.ast.find_all(exp.CTE):
            if cte.alias_or_name == table_name:
                return True
        return False

    def _find_table_by_name(self, table_name: str) -> Optional[TableInfo]:
        for (_, name, _), table in self.tables.items():
            if name == table_name:
                return table
        return None

    def _get_join_type_for_table(self, table_node: exp.Table) -> Optional[str]:
        parent = table_node.parent
        while parent:
            if isinstance(parent, exp.Join):
                side = parent.side
                kind = parent.kind
                if side and kind:
                    return f"{side} {kind} JOIN"
                elif side:
                    return f"{side} JOIN"
                elif kind:
                    return f"{kind} JOIN"
                else:
                    return "INNER JOIN"
            parent = parent.parent
        return None

    def _upsert_table(
        self,
        name: str,
        schema: Optional[str],
        alias: Optional[str],
        table_type: TableType,
        join_type: Optional[str] = None,
    ) -> None:
        if schema == "":
            schema = None
        if alias == "":
            alias = None
        key = (schema, name, table_type)
        if key not in self.tables:
            self.tables[key] = TableInfo(name=name, schema=schema, table_type=table_type)
        self.tables[key].add_alias(alias)
        if join_type and self.tables[key].join_type is None:
            self.tables[key].join_type = join_type

    def _render_columns_sample(self, columns: List[ColumnMetadata]) -> str:
        lines = [
            "Полное имя | Алиасы | Таблица | Где используется | Количество упоминаний",
            "-" * 85,
        ]
        for col in sorted(columns, key=lambda c: (c.table or "", c.column_name)):
            lines.append(
                f"{col.full_name} | {', '.join(col.aliases)} | {col.table or ''} | "
                f"{', '.join(col.usage_locations)} | {col.usage_count}"
            )
        return "\n".join(lines)


class ParserStrategy:
    def parse(self, sql: str) -> SQLMetadata:
        raise NotImplementedError


class SQLGlotParserStrategy(ParserStrategy):
    def __init__(self, dialect: SQLDialect = SQLDialect.ORACLE):
        self.dialect = dialect
        self.preprocessor = SQLPreprocessor(dialect=dialect)

    def parse(self, sql: str) -> SQLMetadata:
        metadata = SQLMetadata(original_sql=sql)
        if not sql.strip():
            metadata.parse_errors.append("SQL запрос пустой")
            return metadata
        try:
            processed_sql = self.preprocessor.preprocess(sql)
            ast = parse_one(processed_sql, dialect=dialect_to_sqlglot(self.dialect))
            analyzer = DetailedColumnAnalyzer(ast, original_sql=sql)
            columns, tables, sample_output = analyzer.analyze()
            metadata.columns = columns
            metadata.tables = tables
            metadata.sample_columns_output = sample_output
        except Exception as exc:
            metadata.parse_errors.append(f"Ошибка парсинга: {exc}")
        return metadata


# =============================================================================
# 6. НОРМАЛИЗАЦИЯ SQL (двойные пробелы -> перенос строки)
# =============================================================================

def normalize_sql_for_parsing(sql: str) -> str:
    """
    Нормализует SQL-запрос перед парсингом.

    Если SQL записан одной строкой и содержит двойные пробелы (как разделители
    между элементами запроса), заменяет каждый двойной пробел на перенос строки.

    Пример:
        'select  t,  t2  from  tt' -> 'select\\nt,\\nt2\\nfrom tt'
    """
    if not sql:
        return sql

    # 1. Унификация окончаний строк
    sql = sql.replace('\r\n', '\n')

    # 2. Если SQL не содержит переносов строк, но содержит двойные пробелы
    if '\n' not in sql and '  ' in sql:
        # Заменяем двойные пробелы на перенос строки
        sql = sql.replace('  ', '\n')

    # 3. Удаляем лишние пробелы в начале/конце каждой строки
    lines = [line.strip() for line in sql.split('\n')]

    # 4. Схлопываем множественные пустые строки
    cleaned = []
    for line in lines:
        if line or (cleaned and cleaned[-1]):
            cleaned.append(line)

    return '\n'.join(cleaned).strip()


# =============================================================================
# 7. АВТООПРЕДЕЛЕНИЕ ДИАЛЕКТА SQL
# =============================================================================

# Порядок перебора диалектов
DIALECT_PRIORITY = ['oracle', 'tsql', 'postgres']


def parse_sql_with_dialect_auto(sql: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Пытается распарсить SQL последовательно разными диалектами.

    Args:
        sql: Нормализованный SQL-запрос.

    Returns:
        Кортеж (AST, dialect_name) или (None, None) если ни один диалект не подошёл.
    """
    for dialect_name in DIALECT_PRIORITY:
        try:
            ast = parse_one(sql, dialect=dialect_name)
            return ast, dialect_name
        except Exception:
            continue
    return None, None


# =============================================================================
# 8. ОБРАБОТКА DATAFRAME
# =============================================================================

def extract_metadata_from_sql(sql: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Извлекает метаданные из SQL-запроса с автоопределением диалекта.

    Args:
        sql: Исходный SQL-запрос.

    Returns:
        Кортеж (список словарей с метаданными, имя диалекта).
    """
    if not sql or not sql.strip():
        return [], ''

    # Нормализация
    normalized_sql = normalize_sql_for_parsing(sql)

    # Автоопределение диалекта
    ast, dialect_name = parse_sql_with_dialect_auto(normalized_sql)
    if ast is None:
        return [], ''

    # Парсинг через SQLGlotParserStrategy с определённым диалектом
    dialect_enum = {
        'oracle': SQLDialect.ORACLE,
        'tsql': SQLDialect.SQLSERVER,
        'postgres': SQLDialect.POSTGRESQL,
    }.get(dialect_name, SQLDialect.ORACLE)

    parser = SQLGlotParserStrategy(dialect=dialect_enum)
    metadata = parser.parse(normalized_sql)

    if metadata.parse_errors:
        return [], dialect_name

    # Формируем плоский список записей
    results = []
    for col in metadata.columns:
        # Определяем тип таблицы
        table_type = ''
        table_schema = ''
        table_name = col.table or ''
        table_alias = col.table_alias or ''

        # Ищем информацию о таблице в метаданных
        if col.table:
            for t in metadata.tables:
                if t.name == col.table or (col.table_alias and t.name == col.table_alias):
                    table_type = t.table_type.value
                    table_schema = t.schema or ''
                    table_alias = ', '.join(sorted(t.aliases)) if t.aliases else (col.table_alias or '')
                    break

        results.append({
            'col_name': col.column_name,
            'table_schema': table_schema,
            'table_name': table_name,
            'table_type': table_type,
            'table_alias': table_alias,
            'col_full_name': col.full_name or col.column_name,
        })

    return results, dialect_name


def process_dataframe_v2(
    df: pd.DataFrame,
    sql_column: str = 'SQL_TEXT',
) -> pd.DataFrame:
    """
    Обрабатывает датафрейм с SQL-запросами.

    Args:
        df: DataFrame с колонками REP_ID, DP_ID, SQL_TEXT.
        sql_column: Имя колонки с SQL (по умолчанию 'SQL_TEXT').

    Returns:
        DataFrame с распарсенными метаданными.
    """
    keep_columns = ['REP_ID', 'DP_ID']
    results = []

    for idx, row in df.iterrows():
        sql = row.get(sql_column, "")
        if not sql or not isinstance(sql, str):
            continue

        rep_id = row.get('REP_ID', '')
        dp_id = row.get('DP_ID', '')
        key = f"{rep_id}_{dp_id}"

        mappings, dialect_name = extract_metadata_from_sql(sql)

        if not mappings:
            # Ошибка парсинга
            base_row = {}
            for col in keep_columns:
                if col in row:
                    base_row[col] = row.get(col, "")
            results.append({
                **base_row,
                'KEY': key,
                'col_name': 'ERROR',
                'table_schema': '',
                'table_name': '',
                'table_type': 'parse_error',
                'table_alias': '',
                'col_full_name': 'ERROR',
                'dialect': dialect_name or '',
            })
            continue

        for mapping in mappings:
            base_row = {}
            for col in keep_columns:
                if col in row:
                    base_row[col] = row.get(col, "")
            results.append({
                **base_row,
                'KEY': key,
                **mapping,
                'dialect': dialect_name or '',
            })

    return pd.DataFrame(results)


# =============================================================================
# 9. РАБОТА С ORACLE
# =============================================================================

def create_results_table(cursor, table_name: str) -> None:
    """Создаёт таблицу для результатов парсинга."""
    create_sql = f"""
    CREATE TABLE {table_name} (
        LOAD_DATE      TIMESTAMP,
        KEY            VARCHAR2(200),
        REP_ID         NUMBER,
        DP_ID          VARCHAR2(100),
        COL_NAME       VARCHAR2(1000),
        TABLE_SCHEMA   VARCHAR2(1000),
        TABLE_NAME     VARCHAR2(1000),
        TABLE_TYPE     VARCHAR2(100),
        TABLE_ALIAS    VARCHAR2(1000),
        COL_FULL_NAME  VARCHAR2(2000),
        DIALECT        VARCHAR2(50)
    )
    """
    cursor.execute(create_sql)
    print(f"Таблица {table_name} создана.")


def insert_results(cursor, connection, table_name: str, result_df: pd.DataFrame) -> None:
    """Вставляет данные в таблицу результатов пачками."""
    insert_sql = f"""
    INSERT INTO {table_name} (
        LOAD_DATE, KEY, REP_ID, DP_ID,
        COL_NAME, TABLE_SCHEMA, TABLE_NAME,
        TABLE_TYPE, TABLE_ALIAS, COL_FULL_NAME, DIALECT
    ) VALUES (
        :1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11
    )
    """

    data_to_insert = []
    for _, row in result_df.iterrows():
        data_to_insert.append((
            row.get('LOAD_DATE', datetime.now()),
            row.get('KEY', ''),
            row.get('REP_ID', None),
            row.get('DP_ID', ''),
            row.get('col_name', ''),
            row.get('table_schema', ''),
            row.get('table_name', ''),
            row.get('table_type', ''),
            row.get('table_alias', ''),
            row.get('col_full_name', ''),
            row.get('dialect', ''),
        ))

    batch_size = 100
    for i in range(0, len(data_to_insert), batch_size):
        batch = data_to_insert[i:i + batch_size]
        cursor.executemany(insert_sql, batch)
        connection.commit()
        print(f"  Вставлено {len(batch)} записей")


# =============================================================================
# 10. ОСНОВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    """Основная функция скрипта."""
    # Загрузка конфигурации
    config = load_config()
    db_user = config['db_user']
    db_pass = config['db_pass']
    db_dsn = config['db_dsn']
    providers_table = config['providers_table']
    results_table = config['results_table']

    connection = None
    try:
        # Подключение к БД
        print(f"Подключение к БД {db_dsn}...")
        connection = cx_Oracle.connect(db_user, db_pass, db_dsn)
        cursor = connection.cursor()

        # Обработчик CLOB для чтения длинных текстов
        def output_type_handler(curs, name, default_type, size, precision, scale):
            if default_type == cx_Oracle.CLOB:
                return curs.var(cx_Oracle.LONG_STRING, arraysize=curs.arraysize)
            return curs.var(default_type, size, curs.arraysize)
        cursor.outputtypehandler = output_type_handler

        # Получение данных из таблицы провайдеров
        print(f"Чтение данных из {providers_table}...")
        query = f"""
        SELECT REP_ID, DP_ID, SQL_TEXT
        FROM {providers_table}
        WHERE SQL_TEXT IS NOT NULL
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("Нет данных для обработки.")
            return

        # Создание DataFrame
        df = pd.DataFrame(rows, columns=['REP_ID', 'DP_ID', 'SQL_TEXT'])
        print(f"Получено {len(df)} записей для обработки")

        # Обработка SQL
        print("Начало парсинга SQL...")
        result_df = process_dataframe_v2(df, sql_column='SQL_TEXT')

        if result_df.empty:
            print("Результатов парсинга нет.")
            return

        # Добавление даты загрузки
        load_date = datetime.now()
        result_df['LOAD_DATE'] = load_date

        # Переименование колонок для соответствия требованиям
        result_df = result_df.rename(columns={
            'table_schema': 'TABLE_SCHEMA',
            'dialect': 'DIALECT',
        })

        # Проверка существования таблицы результатов
        cursor.execute(f"""
            SELECT COUNT(*) FROM user_tables
            WHERE table_name = '{results_table.upper()}'
        """)
        table_exists = cursor.fetchone()[0] > 0

        if table_exists:
            print(f"Таблица {results_table} существует. Добавление новых данных...")
        else:
            print(f"Создание новой таблицы {results_table}...")
            create_results_table(cursor, results_table)

        # Вставка данных
        insert_results(cursor, connection, results_table, result_df)

        print(f"Готово. Всего обработано записей: {len(result_df)}")
        cursor.close()

    except cx_Oracle.DatabaseError as e:
        print(f"Ошибка БД: {e}")
        if connection:
            connection.rollback()
    except Exception as e:
        print(f"Общая ошибка: {e}")
        traceback.print_exc()
    finally:
        if connection:
            try:
                connection.close()
                print("Соединение с Oracle закрыто.")
            except Exception:
                pass


if __name__ == "__main__":
    main()