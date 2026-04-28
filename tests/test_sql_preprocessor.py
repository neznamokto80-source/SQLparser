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
