from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sql_parser import SQLPreprocessor


def test_preprocessor_removes_comments_and_keeps_select():
    sql = "SELECT * FROM users -- comment\nWHERE id = 1"
    result = SQLPreprocessor().preprocess(sql)
    assert "--" not in result
    assert "SELECT" in result.upper()


def test_preprocessor_replaces_convert_and_to_date():
    sql = "SELECT CONVERT(date, x) AS d, to_date('2024-01-01','YYYY-MM-DD') AS dt FROM t"
    result = SQLPreprocessor().preprocess(sql)
    assert "CONVERT" not in result.upper()
    assert "TO_DATE" not in result.upper()
    assert "CAST" in result.upper()


def test_preprocessor_handles_convert_with_dotted_column():
    """CONVERT с varchar и именем колонки, содержащим точку."""
    sql = "SELECT CONVERT(varchar(30), BillStockMoveStock.id) FROM Bills"
    result = SQLPreprocessor().preprocess(sql)
    assert "CONVERT" not in result.upper()
    assert "CAST" in result.upper()
    assert "BillStockMoveStock.id" in result


def test_preprocessor_handles_spaces_in_in_clause():
    """Пробел перед ) в NOT IN."""
    sql = "SELECT col FROM t WHERE col NOT IN ('DEL' )"
    result = SQLPreprocessor().preprocess(sql)
    assert "('DEL')" in result


def test_preprocessor_full_query():
    """Полный запрос из задачи."""
    sql = """SELECT
         Bills.doc_number,
         Bills.doc_date,
         CONVERT(varchar(30), BillStockMoveStock.id)
FROM Bills WHERE 1=1
         AND BillDetailsItemStates.state_code NOT IN ('DEL' )
         AND Bills.doc_date > '09/01/2016 00:0:0'
      AND Bills.doc_date <= '10/01/2016 00:0:0'"""
    result = SQLPreprocessor().preprocess(sql)
    assert "CONVERT" not in result.upper()
    assert "CAST" in result.upper()
    assert "('DEL')" in result
