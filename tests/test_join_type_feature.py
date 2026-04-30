"""
Тестирование извлечения типа JOIN и его отображения в метаданных.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from core.column_analyzer import DetailedColumnAnalyzer
from models.sql_metadata import TableType
import sqlglot as sg


def test_join_type_extraction():
    """Проверяет, что тип JOIN правильно извлекается для таблиц."""
    sql = """
    SELECT a.id, b.name, c.value
    FROM table_a a
    LEFT JOIN table_b b ON a.id = b.a_id
    INNER JOIN table_c c ON b.id = c.b_id
    RIGHT OUTER JOIN table_d d ON c.id = d.c_id
    """
    ast = sg.parse_one(sql)
    analyzer = DetailedColumnAnalyzer(ast)
    columns, tables, sample = analyzer.analyze()
    
    # Проверяем, что таблицы найдены
    table_names = {t.name for t in tables}
    assert "table_a" in table_names
    assert "table_b" in table_names
    assert "table_c" in table_names
    assert "table_d" in table_names
    
    # Проверяем join_type для каждой таблицы
    join_types = {}
    for t in tables:
        join_types[t.name] = t.join_type
    
    # table_a - не участвует в JOIN (FROM)
    assert join_types.get("table_a") is None or join_types["table_a"] == ""
    
    # table_b - LEFT JOIN
    assert join_types.get("table_b") == "LEFT JOIN"
    
    # table_c - INNER JOIN
    assert join_types.get("table_c") == "INNER JOIN"
    
    # table_d - RIGHT OUTER JOIN
    assert join_types.get("table_d") == "RIGHT OUTER JOIN"
    
    print("PASS: test_join_type_extraction")


def test_join_type_with_aliases():
    """Проверяет тип JOIN с алиасами таблиц."""
    sql = """
    SELECT u.id, o.amount
    FROM users u
    LEFT OUTER JOIN orders o ON u.id = o.user_id
    """
    ast = sg.parse_one(sql)
    analyzer = DetailedColumnAnalyzer(ast)
    columns, tables, sample = analyzer.analyze()
    
    for t in tables:
        if t.name == "orders":
            assert t.join_type == "LEFT OUTER JOIN"
            break
    else:
        assert False, "Таблица orders не найдена"
    
    print("PASS: test_join_type_with_aliases")


def test_join_type_no_join():
    """Запрос без JOIN должен иметь пустой join_type."""
    sql = "SELECT id FROM users"
    ast = sg.parse_one(sql)
    analyzer = DetailedColumnAnalyzer(ast)
    columns, tables, sample = analyzer.analyze()
    
    for t in tables:
        assert t.join_type is None or t.join_type == ""
    
    print("PASS: test_join_type_no_join")


def test_join_type_multiple_joins_same_table():
    """Если таблица участвует в нескольких JOIN (например, self-join),
    должен сохраниться первый обнаруженный тип (или какой-то)."""
    sql = """
    SELECT t1.id, t2.id
    FROM mytable t1
    INNER JOIN mytable t2 ON t1.parent = t2.id
    """
    ast = sg.parse_one(sql)
    analyzer = DetailedColumnAnalyzer(ast)
    columns, tables, sample = analyzer.analyze()
    
    # Ожидаем две записи таблицы mytable? В текущей реализации они объединяются в одну,
    # потому что схема и имя одинаковые, тип таблицы TABLE. join_type может быть INNER JOIN.
    # Проверим, что join_type установлен.
    for t in tables:
        if t.name == "mytable":
            assert t.join_type == "INNER JOIN"
            break
    
    print("PASS: test_join_type_multiple_joins_same_table")


def test_join_without_type_is_inner():
    """JOIN без указания типа (просто JOIN) должен интерпретироваться как INNER JOIN."""
    sql = """
    SELECT a.id, b.name
    FROM table_a a
    JOIN table_b b ON a.id = b.a_id
    """
    ast = sg.parse_one(sql)
    analyzer = DetailedColumnAnalyzer(ast)
    columns, tables, sample = analyzer.analyze()
    
    # Находим таблицу table_b (участвует в JOIN)
    for t in tables:
        if t.name == "table_b":
            assert t.join_type == "INNER JOIN"
            break
    else:
        assert False, "Таблица table_b не найдена"
    
    print("PASS: test_join_without_type_is_inner")


def test_oracle_outer_join_with_alias():
    """Проверяет обнаружение Oracle-синтаксиса (+) с алиасами таблиц."""
    sql = """
    SELECT e.ename, d.dname
    FROM emp e, dept d
    WHERE e.deptno = d.deptno(+)
    """
    ast = sg.parse_one(sql, dialect="oracle")
    analyzer = DetailedColumnAnalyzer(ast, original_sql=sql)
    columns, tables, sample = analyzer.analyze()
    
    # Находим таблицу dept (с алиасом d) - она должна быть LEFT JOIN
    for t in tables:
        if t.name == "dept":
            assert t.join_type == "LEFT JOIN", f"Ожидался LEFT JOIN, получено {t.join_type}"
            break
    else:
        assert False, "Таблица dept не найдена"
    
    # Таблица emp (e) не имеет outer join
    for t in tables:
        if t.name == "emp":
            assert t.join_type is None or t.join_type == "", f"Ожидался пустой join_type, получено {t.join_type}"
            break
    
    print("PASS: test_oracle_outer_join_with_alias")


if __name__ == "__main__":
    test_join_type_extraction()
    test_join_type_with_aliases()
    test_join_type_no_join()
    test_join_type_multiple_joins_same_table()
    test_join_without_type_is_inner()
    test_oracle_outer_join_with_alias()
    print("\nВсе тесты пройдены успешно.")