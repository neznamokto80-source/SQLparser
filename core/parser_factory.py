"""
Factory for creating parser instances.
"""

from __future__ import annotations

from .parser_strategy import ParserStrategy, SQLGlotParserStrategy
from .sql_dialect import SQLDialect


class ParserFactory:
    """Factory for creating parser instances."""

    @staticmethod
    def create_parser(parser_type: str = "sqlglot", **kwargs) -> ParserStrategy:
        """
        Create a parser instance of the requested type.

        Currently only "sqlglot" is supported.

        Args:
            parser_type: Parser type identifier (default: "sqlglot").
            **kwargs: Additional keyword arguments passed to the parser constructor.
                Supported keyword: `dialect` (SQLDialect).

        Returns:
            ParserStrategy instance.

        Raises:
            ValueError: If `parser_type` is not supported.
        """
        if parser_type != "sqlglot":
            raise ValueError(f"Неизвестный тип парсера: {parser_type}")
        return SQLGlotParserStrategy(dialect=kwargs.get("dialect", SQLDialect.ORACLE))