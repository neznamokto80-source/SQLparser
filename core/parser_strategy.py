"""
Abstract parser strategy and concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import re

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from .sql_dialect import SQLDialect, dialect_to_sqlglot
from .sql_preprocessor import SQLPreprocessor
from .column_analyzer import DetailedColumnAnalyzer
from models.sql_metadata import SQLMetadata


class ParserStrategy(ABC):
    """Abstract base class for SQL parser strategies."""

    @abstractmethod
    def parse(self, sql: str) -> SQLMetadata:
        """
        Parse a SQL statement and extract metadata.

        Args:
            sql: SQL string to parse.

        Returns:
            SQLMetadata object containing columns, tables, errors, etc.
        """
        raise NotImplementedError


class SQLGlotParserStrategy(ParserStrategy):
    """Concrete parser strategy using sqlglot library."""

    def __init__(self, dialect: SQLDialect = SQLDialect.ORACLE):
        """
        Initialize sqlglot‑based parser.

        Args:
            dialect: SQL dialect to use for parsing (default: ORACLE).
        """
        self.dialect = dialect
        self.preprocessor = SQLPreprocessor(dialect=dialect)

    def parse(self, sql: str) -> SQLMetadata:
        """
        Parse SQL using sqlglot AST.

        Steps:
        1. Preprocess SQL (remove comments, normalize functions, etc.)
        2. Parse with sqlglot into an AST
        3. Analyze columns, tables, and relationships
        4. Populate metadata object

        Args:
            sql: SQL string to parse.

        Returns:
            SQLMetadata with columns, tables, errors, and JSON schema.
        """
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
            metadata.json_schema = self._json_schema()
            metadata.procedures = self.preprocessor.procedures
            metadata.table_functions = self.preprocessor.table_functions
        except Exception as exc:
            metadata.parse_errors.append(f"Ошибка парсинга: {exc}")
        return metadata

    def _json_schema(self) -> Dict[str, object]:
        """
        Generate JSON Schema describing the structure of SQLMetadata.

        Returns:
            Dictionary conforming to JSON Schema Draft‑7 that documents
            the shape of the metadata returned by the parser.
        """
        return {
            "type": "object",
            "properties": {
                "metadata": {
                    "type": "object",
                    "properties": {
                        "original_sql": {"type": "string"},
                        "statistics": {"type": "object"},
                        "parse_errors": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["original_sql", "statistics", "parse_errors"],
                },
                "tables": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "schema": {"type": ["string", "null"]},
                            "aliases": {"type": "array", "items": {"type": "string"}},
                            "type": {"type": "string"},
                            "column_count": {"type": "integer"},
                        },
                    },
                },
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "full_name": {"type": "string"},
                            "table": {"type": ["string", "null"]},
                            "table_alias": {"type": ["string", "null"]},
                            "column_name": {"type": "string"},
                            "aliases": {"type": "array", "items": {"type": "string"}},
                            "column_aliases": {"type": "array", "items": {"type": "string"}},
                            "usage_locations": {"type": "array", "items": {"type": "string"}},
                            "usage_count": {"type": "integer"},
                            "is_calculation": {"type": "boolean"},
                            "calculation_type": {"type": ["string", "null"]},
                            "calculation_expression": {"type": ["string", "null"]},
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "json_schema": {"type": "object"},
            },
            "required": ["metadata", "tables", "columns", "json_schema"],
        }


def _is_paren_error(error_msg: str) -> bool:
    """Checks if the error message is an unbalanced parenthesis error."""
    return "Expecting )" in error_msg or "Expecting)." in error_msg or "Expecting (" in error_msg


def _is_case_error(error_msg: str) -> bool:
    """Checks if the error message is an unclosed CASE error."""
    msg = error_msg.lower()
    return "expected end" in msg and "case" in msg


def _is_between_error(error_msg: str) -> bool:
    """Checks if the error is an incomplete BETWEEN expression."""
    msg = error_msg.lower()
    return "required keyword" in msg and "'high'" in msg


def _try_fix_case(sql: str, dialect_sqlglot: str) -> str | None:
    """Fixes unclosed CASE by adding END before clauses."""
    from .sql_preprocessor import SQLPreprocessor
    from .sql_dialect import SQLDialect

    # Determine dialect from string
    dialect_map = {v: k for k, v in {
        SQLDialect.ORACLE: "oracle",
        SQLDialect.POSTGRESQL: "postgres",
        SQLDialect.MYSQL: "mysql",
        SQLDialect.SQLSERVER: "tsql",
    }.items()}
    dialect_enum = dialect_map.get(dialect_sqlglot, SQLDialect.ORACLE)

    preprocessor = SQLPreprocessor(dialect=dialect_enum)
    fixed = preprocessor._fix_case_expressions(sql)

    if fixed == sql:
        return None

    try:
        parse_one(fixed, dialect=dialect_sqlglot)
        return fixed
    except Exception:
        return None


def _try_fix_between(sql: str, dialect_sqlglot: str) -> str | None:
    """Fixes incomplete BETWEEN by adding missing operands."""
    from .sql_preprocessor import SQLPreprocessor
    from .sql_dialect import SQLDialect

    dialect_map = {v: k for k, v in {
        SQLDialect.ORACLE: "oracle",
        SQLDialect.POSTGRESQL: "postgres",
        SQLDialect.MYSQL: "mysql",
        SQLDialect.SQLSERVER: "tsql",
    }.items()}
    dialect_enum = dialect_map.get(dialect_sqlglot, SQLDialect.ORACLE)

    preprocessor = SQLPreprocessor(dialect=dialect_enum)
    fixed = preprocessor._fix_between_expressions(sql)

    if fixed == sql:
        return None

    try:
        parse_one(fixed, dialect=dialect_sqlglot)
        return fixed
    except Exception:
        return None


# Regex for SQL clause keywords
_CLAUSE_RE = re.compile(
    r"\b(FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|UNION|INTERSECT|EXCEPT|LIMIT|FETCH)\b",
    re.IGNORECASE,
)


def _try_insert_parens(sql: str, dialect_sqlglot: str) -> str | None:
    """Fixes unclosed `(` by inserting `)` before clause keywords.

    Single pass through SQL: tracks parenthesis nesting depth. When a clause
    keyword (FROM, WHERE etc.) is found inside an unclosed parenthesis —
    inserts the needed number of `)` before it.

    Returns fixed SQL on successful parse, otherwise None.
    """
    in_string = False
    escape = False
    depth = 0
    inserts: list[int] = []

    for i, ch in enumerate(sql):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == "'":
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth > 0:
                depth -= 1

        # If inside unclosed parenthesis and found a clause keyword — mark insert position
        if depth > 0:
            rest = sql[i:]
            m = _CLAUSE_RE.match(rest)
            if m:
                inserts.append((i, depth))  # (position, how many `)` to insert)
                depth = 0  # all unclosed parens close before this clause

    if not inserts:
        return None

    # Build candidate: insert N closing brackets at each marked position
    result = []
    last = 0
    for pos, count in inserts:
        result.append(sql[last:pos])
        result.append(")" * count + " ")
        last = pos
    result.append(sql[last:])
    candidate = "".join(result)

    try:
        parse_one(candidate, dialect=dialect_sqlglot)
        return candidate
    except Exception:
        return None


class ProgressiveSQLGlotParserStrategy(ParserStrategy):
    """Parser that applies cleaning steps sequentially, stopping at the first
    successful parse. Finds minimal necessary transformations."""

    def __init__(self, dialect: SQLDialect = SQLDialect.ORACLE):
        self.dialect = dialect
        self.preprocessor = SQLPreprocessor(dialect=dialect)
        self.last_applied_steps: list[str] = []
        self.last_cleaned_sql: str = ""

    def _try_parse(self, sql: str) -> SQLMetadata:
        """Attempts to parse SQL and return metadata (or errors).

        If error is related to unbalanced parentheses — automatically inserts
        `)` and retries. If unclosed CASE error — adds END.
        """
        metadata = SQLMetadata(original_sql=sql)
        try:
            ast = parse_one(sql, dialect=dialect_to_sqlglot(self.dialect))
            analyzer = DetailedColumnAnalyzer(ast, original_sql=sql)
            columns, tables, sample_output = analyzer.analyze()
            metadata.columns = columns
            metadata.tables = tables
            metadata.sample_columns_output = sample_output
            metadata.json_schema = {
                "type": "object",
                "properties": {
                    "metadata": {"type": "object"},
                    "tables": {"type": "array"},
                    "columns": {"type": "array"},
                    "json_schema": {"type": "object"},
                },
            }
            return metadata
        except Exception as exc:
            err_msg = str(exc)
            # Fix: unbalanced parenthesis
            if _is_paren_error(err_msg):
                fixed = _try_insert_parens(sql, dialect_to_sqlglot(self.dialect))
                if fixed:
                    try:
                        ast = parse_one(fixed, dialect=dialect_to_sqlglot(self.dialect))
                        analyzer = DetailedColumnAnalyzer(ast, original_sql=sql)
                        columns, tables, sample_output = analyzer.analyze()
                        metadata.columns = columns
                        metadata.tables = tables
                        metadata.sample_columns_output = sample_output
                        metadata.json_schema = {
                            "type": "object",
                            "properties": {
                                "metadata": {"type": "object"},
                                "tables": {"type": "array"},
                                "columns": {"type": "array"},
                                "json_schema": {"type": "object"},
                            },
                        }
                        return metadata
                    except Exception:
                        pass
            # Fix: unclosed CASE
            if _is_case_error(err_msg):
                fixed = _try_fix_case(sql, dialect_to_sqlglot(self.dialect))
                if fixed:
                    try:
                        ast = parse_one(fixed, dialect=dialect_to_sqlglot(self.dialect))
                        analyzer = DetailedColumnAnalyzer(ast, original_sql=sql)
                        columns, tables, sample_output = analyzer.analyze()
                        metadata.columns = columns
                        metadata.tables = tables
                        metadata.sample_columns_output = sample_output
                        metadata.json_schema = {
                            "type": "object",
                            "properties": {
                                "metadata": {"type": "object"},
                                "tables": {"type": "array"},
                                "columns": {"type": "array"},
                                "json_schema": {"type": "object"},
                            },
                        }
                        return metadata
                    except Exception:
                        pass
            # Fix: incomplete BETWEEN
            if _is_between_error(err_msg):
                fixed = _try_fix_between(sql, dialect_to_sqlglot(self.dialect))
                if fixed:
                    try:
                        ast = parse_one(fixed, dialect=dialect_to_sqlglot(self.dialect))
                        analyzer = DetailedColumnAnalyzer(ast, original_sql=sql)
                        columns, tables, sample_output = analyzer.analyze()
                        metadata.columns = columns
                        metadata.tables = tables
                        metadata.sample_columns_output = sample_output
                        metadata.json_schema = {
                            "type": "object",
                            "properties": {
                                "metadata": {"type": "object"},
                                "tables": {"type": "array"},
                                "columns": {"type": "array"},
                                "json_schema": {"type": "object"},
                            },
                        }
                        return metadata
                    except Exception:
                        pass
            metadata.parse_errors.append(err_msg)
        return metadata

    def parse(self, sql: str) -> SQLMetadata:
        """
        Progressive parsing: first tries raw SQL, then applies cleaning steps
        one by one until parsing succeeds or all steps are exhausted.

        Step order:
        1. Without preprocessing (raw SQL)
        2. Remove comments
        3. Remove PL/SQL blocks
        4. Replace <Procedure> XML blocks
        5. Replace TABLE() functions
        6. Replace ODBC {fn ...} functions
        7. Replace CONVERT -> CAST
        8. Replace @variables
        9. Replace TO_DATE functions
        10. Handle star operator
        11. Remove/replace square brackets
        12. Fix typical issues (whitespace etc.)
        """
        self.last_applied_steps = []
        self.last_cleaned_sql = sql

        if not sql or not sql.strip():
            metadata = SQLMetadata(original_sql=sql)
            metadata.parse_errors.append("SQL запрос пустой")
            return metadata

        # Step 0: try parsing raw SQL without preprocessing
        metadata = self._try_parse(sql)
        if not metadata.parse_errors:
            self.last_applied_steps = ["raw"]
            self.last_cleaned_sql = sql
            metadata.procedures = self.preprocessor.procedures
            metadata.table_functions = self.preprocessor.table_functions
            return metadata

        # Steps 1-N: apply each cleaning step sequentially
        for step_name, cleaned_sql in self.preprocessor.preprocess_stepwise(sql):
            self.last_applied_steps.append(step_name)
            self.last_cleaned_sql = cleaned_sql

            metadata = self._try_parse(cleaned_sql)
            if not metadata.parse_errors:
                metadata.procedures = self.preprocessor.procedures
                metadata.table_functions = self.preprocessor.table_functions
                return metadata

        # All steps exhausted — return last error
        metadata.parse_errors.append(
            f"Все шаги очистки применены, парсинг не удался. "
            f"Применены шаги: {', '.join(self.last_applied_steps)}"
        )
        return metadata
