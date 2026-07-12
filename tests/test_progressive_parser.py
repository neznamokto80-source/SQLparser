"""Тесты прогрессивного парсера ProgressiveSQLGlotParserStrategy."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser_factory import ParserFactory
from core.sql_dialect import SQLDialect


def _make_parser():
    return ParserFactory.create_parser("progressive", dialect=SQLDialect.ORACLE)


def test_raw_sql_parses_without_preprocessing():
    """Простой SQL парсится без применения шагов очистки."""
    parser = _make_parser()
    metadata = parser.parse("SELECT a, b FROM users WHERE id = 1")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 2
    assert parser.last_applied_steps == ["raw"]


def test_unclosed_case_auto_fixed():
    """Незакрытый CASE исправляется автоматически."""
    parser = _make_parser()
    metadata = parser.parse("SELECT CASE WHEN x > 0 THEN y FROM t1")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_incomplete_between_auto_fixed():
    """Неполный BETWEEN исправляется автоматически."""
    parser = _make_parser()
    metadata = parser.parse("SELECT a FROM t1 WHERE x BETWEEN 1")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_oracle_hint_removed():
    """Oracle hint /*+ ... */ удаляется."""
    parser = _make_parser()
    metadata = parser.parse("SELECT /*+ FULL(t) */ a FROM t1")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_outer_join_removed():
    """Outer join синтаксис (+) удаляется."""
    parser = _make_parser()
    metadata = parser.parse("SELECT a FROM t1, t2 WHERE t1.id = t2.id(+)")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_odbc_function_replaced():
    """ODBC {fn NOW()} заменяется на CURRENT_TIMESTAMP."""
    parser = _make_parser()
    metadata = parser.parse("SELECT {fn NOW()} FROM t1")
    assert not metadata.parse_errors


def test_convert_to_cast():
    """CONVERT заменяется на CAST."""
    parser = _make_parser()
    metadata = parser.parse("SELECT CONVERT(datetime, col1) FROM t1")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_variable_replaced():
    """@переменные заменяются на заглушки."""
    parser = _make_parser()
    metadata = parser.parse("SELECT col1 FROM t1 WHERE x = @var")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_empty_sql_returns_error():
    """Пустой SQL возвращает ошибку."""
    parser = _make_parser()
    metadata = parser.parse("")
    assert metadata.parse_errors


def test_plsql_block_stripped():
    """PL/SQL блок отсекается, остаётся SELECT."""
    parser = _make_parser()
    metadata = parser.parse("DECLARE x NUMBER; BEGIN NULL; END;\n/\nSELECT a FROM t1")
    assert not metadata.parse_errors
    assert len(metadata.columns) >= 1


def test_steps_recorded():
    """Применённые шаги записываются в last_applied_steps."""
    parser = _make_parser()
    parser.parse("SELECT a FROM t1")
    assert isinstance(parser.last_applied_steps, list)
    assert len(parser.last_applied_steps) >= 1


def test_procedures_captured():
    """Процедуры из <Procedure> блоков сохраняются в metadata."""
    parser = _make_parser()
    sql = 'SELECT a FROM <Procedure qualifier="dbo" name="my_proc" type="StoredProcedure">code</Procedure>'
    metadata = parser.parse(sql)
    assert len(metadata.procedures) >= 1
