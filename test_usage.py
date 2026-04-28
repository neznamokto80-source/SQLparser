from __future__ import annotations

import sys
sys.path.append('.')
from core.sql_parser import ParserFactory, SQLDialect

sql = """
WITH emp_stats AS (
    SELECT 
        e.employee_id,
        e.first_name,
        e.last_name,
        e.department_id,
        e.salary,
        e.hire_date,
        d.department_name,
        -- Ранжирование по отделам
        ROW_NUMBER() OVER (PARTITION BY e.department_id ORDER BY e.salary DESC) AS rank_in_dept,
        -- Скользящее среднее за последние 3 месяца (гипотетическое)
        AVG(e.salary) OVER (PARTITION BY e.department_id 
                            ORDER BY e.hire_date 
                            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_avg_salary,
        -- Разница с максимальной зарплатой в отделе
        MAX(e.salary) OVER (PARTITION BY e.department_id) - e.salary AS diff_from_max
    FROM employees e
    JOIN departments d ON e.department_id = d.department_id
    WHERE e.hire_date >= ADD_MONTHS(SYSDATE, -:months_back) -- параметр
)
SELECT 
    emp_stats.department_name,
    emp_stats.employee_id,
    emp_stats.last_name,
    emp_stats.salary,
    emp_stats.moving_avg_salary,
    emp_stats.diff_from_max
FROM emp_stats
WHERE rank_in_dept <= :top_n  -- параметр
ORDER BY department_name, rank_in_dept;
"""

parser = ParserFactory.create_parser(dialect=SQLDialect.ORACLE)
metadata = parser.parse(sql)

print("Columns:")
for col in metadata.columns:
    print(f"  {col.full_name}: usage_count={col.usage_count}, usage_locations={col.usage_locations}, aliases={col.aliases}")

print("\nSample output:")
print(metadata.sample_columns_output)