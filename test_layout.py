#!/usr/bin/env python3
"""
Тестирование улучшенного layout графа зависимостей.
Генерирует графы для сложного SQL запроса с разными алгоритмами размещения.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.lineage_graph import render_graph_to_file
from core.sql_parser import ParserFactory

def main():
    sql = """
    WITH cte AS (
        SELECT 
            u.id AS user_id,
            u.name,
            COUNT(o.order_id) AS order_count,
            SUM(o.amount) AS total_amount,
            AVG(o.amount) AS avg_amount
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.active = 1
        GROUP BY u.id, u.name
    )
    SELECT 
        user_id,
        name,
        order_count,
        total_amount,
        avg_amount,
        total_amount / NULLIF(order_count, 0) AS avg_per_order
    FROM cte
    ORDER BY total_amount DESC
    """
    parser = ParserFactory.create_parser("sqlglot")
    metadata = parser.parse(sql)
    print(f"Колонок: {len(metadata.columns)}")
    print(f"Таблиц: {len(metadata.tables)}")
    
    layouts = ["spring", "circular", "kamada_kawai", "planar"]
    for layout in layouts:
        filename = f"test_layout_{layout}.png"
        try:
            path = render_graph_to_file(
                metadata,
                filename,
                layout=layout,
                k=2.5 if layout == "spring" else 2.0,
                iterations=150,
                scale=2.5,
                node_size=3500,
                font_size=9,
                figsize=(18, 14)
            )
            print(f"Создан {path} (layout={layout})")
        except Exception as e:
            print(f"Ошибка при создании {layout}: {e}")
    
    # Также создадим граф с увеличенным k для spring
    path = render_graph_to_file(
        metadata,
        "test_layout_spring_high_k.png",
        layout="spring",
        k=5.0,
        iterations=200,
        node_size=3000,
        figsize=(20, 16)
    )
    print(f"Создан {path} с k=5.0")
    
    print("\nВсе графы сохранены в текущей директории.")

if __name__ == "__main__":
    main()