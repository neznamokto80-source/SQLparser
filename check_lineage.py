#!/usr/bin/env python3
"""
Проверка зависимостей колонок для заданного SQL запроса.
"""
import sys
sys.path.append('.')

from core.sql_parser import ParserFactory, SQLDialect

sql = """
-- Пример сложного SQL запроса с несколькими алиасами
SELECT
    u.id AS user_id,
    u.name AS user_name,
    u.email,
    d.department_name,
    COUNT(o.order_id)+SUM(o.amount) as total_orders,
    SUM(o.amount) as total_amount,
    AVG(o.amount) as avg_order_amount
FROM users u
INNER JOIN departments d ON u.dept_id = d.id
LEFT JOIN orders o ON u.id = o.user_id
LEFT JOIN (SELECT table2.t2, table2.t3 FROM table2) tt ON tt.t2 = o.user_id
LEFT JOIN table3 t3a ON t3a.id = u.id
LEFT JOIN table3 t3b ON t3b.id = d.id
WHERE u.active = 1
    AND d.location IN ('Moscow', 'Saint-Petersburg')
    AND o.order_date >= DATE '2023-01-01'
GROUP BY u.id, u.name, u.email, d.department_name
HAVING COUNT(o.order_id) > 5
    AND SUM(o.amount) > 10000
ORDER BY total_amount DESC, user_name ASC
"""

parser = ParserFactory.create_parser(dialect=SQLDialect.ORACLE)
metadata = parser.parse(sql)

print("Колонки и их зависимости:")
for col in metadata.columns:
    print(f"  {col.full_name or col.column_name}:")
    print(f"    таблица: {col.table}")
    print(f"    вычисляемая: {col.is_calculation}, тип: {col.calculation_type}")
    print(f"    зависимости: {col.dependencies}")
    print()