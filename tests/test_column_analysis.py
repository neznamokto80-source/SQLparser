from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sql_parser import ParserFactory, SQLDialect


def _find_column(metadata, full_name):
    for col in metadata.columns:
        if col.full_name == full_name:
            return col
    return None


def test_usage_contexts_and_counts_for_complex_query():
    sql = """
    SELECT
        u.id AS user_id,
        u.name AS user_name,
        COUNT(o.order_id) as total_orders,
        SUM(o.amount) as total_amount
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    WHERE u.active = 1
    GROUP BY u.id, u.name
    HAVING COUNT(o.order_id) > 5
    ORDER BY user_id
    """
    parser = ParserFactory.create_parser("sqlglot", dialect=SQLDialect.ORACLE)
    metadata = parser.parse(sql)
    col = _find_column(metadata, "users.id")
    assert col is not None
    assert "u.id" in col.aliases
    assert "user_id" in col.aliases
    assert {"SELECT", "JOIN", "GROUP BY", "ORDER BY"}.issubset(set(col.usage_locations))
    assert col.usage_count == 4


def test_calculation_detection_and_type():
    sql = "SELECT SUM(o.amount) AS total_amount FROM orders o GROUP BY o.customer_id"
    parser = ParserFactory.create_parser("sqlglot", dialect=SQLDialect.ORACLE)
    metadata = parser.parse(sql)
    amount_col = _find_column(metadata, "orders.amount")
    assert amount_col is not None
    assert amount_col.is_calculation is True
    assert amount_col.calculation_type in ("SUM", "AGGFUNC", "SUMFUNC")
    assert "calculation" in amount_col.usage_locations


def test_join_using_columns_not_ignored():
    sql = "SELECT a.id FROM accounts a JOIN users u USING (id)"
    parser = ParserFactory.create_parser("sqlglot", dialect=SQLDialect.ORACLE)
    metadata = parser.parse(sql)
    accounts_id = _find_column(metadata, "accounts.id")
    users_id = _find_column(metadata, "users.id")
    assert accounts_id is not None
    assert users_id is not None
    assert "JOIN" in accounts_id.usage_locations
    assert "JOIN" in users_id.usage_locations


def test_cte_and_subquery_processing():
    sql = """
    WITH base AS (
        SELECT u.id, u.name FROM users u
    )
    SELECT b.id FROM base b
    WHERE b.id IN (SELECT o.user_id FROM orders o)
    """
    parser = ParserFactory.create_parser("sqlglot", dialect=SQLDialect.ORACLE)
    metadata = parser.parse(sql)
    table_names = {t.name for t in metadata.get_unique_tables()}
    assert "base" in table_names
    assert "orders" in table_names
    assert _find_column(metadata, "base.id") is not None


def test_alias_list_contains_only_real_aliases():
    sql = """
    SELECT
        u.id AS user_id,
        u.name AS user_name
    FROM users u
    LEFT JOIN (SELECT table2.t2, table2.t3 FROM table2) tt ON tt.t2 = u.id
    """
    parser = ParserFactory.create_parser("sqlglot", dialect=SQLDialect.ORACLE)
    metadata = parser.parse(sql)

    users_id = _find_column(metadata, "users.id")
    assert users_id is not None
    assert "u.id" in users_id.aliases
    assert "user_id" in users_id.aliases
    assert "users.id" not in users_id.aliases

    table2_t3 = _find_column(metadata, "table2.t3")
    assert table2_t3 is not None
    assert "tt.t3" in table2_t3.aliases
    assert "table2.t3" not in table2_t3.aliases
