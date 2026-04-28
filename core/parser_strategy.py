"""
Abstract parser strategy and concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from sqlglot import exp, parse_one

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
            analyzer = DetailedColumnAnalyzer(ast)
            columns, tables, sample_output = analyzer.analyze()
            metadata.columns = columns
            metadata.tables = tables
            metadata.sample_columns_output = sample_output
            metadata.json_schema = self._json_schema()
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