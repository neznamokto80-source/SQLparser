"""
Factory for creating parser instances.
"""

from __future__ import annotations

from .parser_strategy import ParserStrategy, SQLGlotParserStrategy, ProgressiveSQLGlotParserStrategy
from .sql_dialect import SQLDialect


class ParserFactory:
    """Factory for creating parser instances."""

    @staticmethod
    def create_parser(parser_type: str = "sqlglot", **kwargs) -> ParserStrategy:
        """
        Create a parser instance of the requested type.

        Currently supports "sqlglot" and "progressive" parser types.

        Args:
            parser_type: Parser type identifier (default: "sqlglot").
            **kwargs: Additional keyword arguments passed to the parser constructor.
                Supported keyword: `dialect` (SQLDialect).

        Returns:
            ParserStrategy instance.

        Raises:
            ValueError: If `parser_type` is not supported.
        """
        dialect = kwargs.get("dialect", SQLDialect.ORACLE)
        if parser_type == "sqlglot":
            return SQLGlotParserStrategy(dialect=dialect)
        if parser_type == "progressive":
            return ProgressiveSQLGlotParserStrategy(dialect=dialect)
        raise ValueError(f"Неизвестный тип парсера: {parser_type}")
