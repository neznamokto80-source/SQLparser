"""
SQL parser facade – re‑exports the split‑out modules for backward compatibility.
"""

from __future__ import annotations

from .sql_dialect import SQLDialect, dialect_to_sqlglot
from .sql_preprocessor import SQLPreprocessor
from .parser_strategy import ParserStrategy, SQLGlotParserStrategy, ProgressiveSQLGlotParserStrategy
from .column_analyzer import DetailedColumnAnalyzer, CALCULATION_NODES, ScopeInfo
from .parser_factory import ParserFactory

__all__ = [
    "SQLDialect",
    "dialect_to_sqlglot",
    "SQLPreprocessor",
    "ParserStrategy",
    "SQLGlotParserStrategy",
    "ProgressiveSQLGlotParserStrategy",
    "DetailedColumnAnalyzer",
    "CALCULATION_NODES",
    "ScopeInfo",
    "ParserFactory",
]
