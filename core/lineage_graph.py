"""
Генерация графа зависимостей (lineage) колонок SQL с использованием NetworkX и Matplotlib.
"""
from __future__ import annotations

import io
import tempfile
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.figure import Figure

from models.sql_metadata import ColumnMetadata, SQLMetadata


def build_lineage_graph(
    metadata: SQLMetadata,
    layout: str = "spring",
    node_size: int = 3000,
    font_size: int = 10,
    **kwargs,
) -> Tuple[nx.DiGraph, dict]:
    """Строит ориентированный граф зависимостей между колонками.

    Узлы графа — колонки (с полным именем). Рёбра идут от зависимых колонок
    к тем, от которых они зависят (dependencies). Вычисляемые колонки выделяются
    цветом.

    Args:
        metadata: Метаданные SQL запроса.
        layout: Алгоритм размещения узлов ('spring', 'circular', 'kamada_kawai', 'planar').
        node_size: Размер узлов в пикселях.
        font_size: Размер шрифта меток узлов.
        **kwargs: Дополнительные параметры для layout (k, iterations, scale).

    Returns:
        Кортеж (граф networkx.DiGraph, словарь атрибутов узлов).
    """
    G = nx.DiGraph()
    node_attrs = {}

    # Добавляем узлы для всех колонок
    for col in metadata.columns:
        node_id = col.full_name or f"{col.table}.{col.column_name}" if col.table else col.column_name
        label_lines = [col.column_name]
        if col.table:
            label_lines.append(f"({col.table})")
        if col.is_calculation:
            label_lines.append(f"[{col.calculation_type}]")
        label = "\n".join(label_lines)

        # Настройка цвета в зависимости от типа колонки
        if col.is_calculation:
            color = "#ffccbc"  # светло-оранжевый
            text_color = "#bf360c"
        elif col.table is None or col.table == "UNKNOWN":
            color = "#f5f5f5"  # светло-серый
            text_color = "#616161"
        else:
            color = "#e0f7fa"  # светло-голубой
            text_color = "#006064"

        G.add_node(node_id)
        node_attrs[node_id] = {
            "label": label,
            "color": color,
            "text_color": text_color,
            "shape": "s",  # квадрат
        }

    # Добавляем рёбра из зависимостей
    for col in metadata.columns:
        src_id = col.full_name or f"{col.table}.{col.column_name}" if col.table else col.column_name
        for dep in col.dependencies:
            # Зависимость может быть полным именем или просто именем колонки
            # Пытаемся найти соответствующую колонку в метаданных
            target_id = None
            for c in metadata.columns:
                if c.full_name == dep or (c.table and f"{c.table}.{c.column_name}" == dep):
                    target_id = c.full_name or f"{c.table}.{c.column_name}" if c.table else c.column_name
                    break
            if target_id is None:
                # Если не нашли, создаём узел для зависимости
                target_id = dep
                G.add_node(target_id)
                node_attrs[target_id] = {
                    "label": dep,
                    "color": "#f5f5f5",
                    "text_color": "#616161",
                    "shape": "s",
                }
            G.add_edge(src_id, target_id)

    return G, node_attrs


def render_graph_to_bytes(
    metadata: SQLMetadata,
    output_format: str = "png",
    dpi: int = 100,
    figsize: Tuple[int, int] = (16, 12),
    **kwargs,
) -> bytes:
    """Генерирует граф и возвращает его в виде байтов изображения.

    Args:
        metadata: Метаданные SQL запроса.
        output_format: Формат вывода (png, svg, pdf). Поддерживается только PNG.
        dpi: Разрешение изображения.
        figsize: Размер фигуры (ширина, высота) в дюймах.
        **kwargs: Дополнительные аргументы для build_lineage_graph и layout:
            - layout: алгоритм размещения ('spring', 'circular', 'kamada_kawai', 'planar')
            - k: сила отталкивания для spring layout (по умолчанию 2.0)
            - iterations: количество итераций для spring layout (по умолчанию 100)
            - scale: масштаб для circular layout (по умолчанию 2.0)
            - node_size: размер узлов в пикселях (по умолчанию 3000)
            - font_size: размер шрифта меток узлов (по умолчанию 10)

    Returns:
        Байты изображения графа.
    """
    if output_format.lower() != "png":
        raise ValueError("Поддерживается только PNG формат")

    G, node_attrs = build_lineage_graph(metadata, **kwargs)

    # Выбираем layout с улучшенными параметрами
    layout_algo = kwargs.get("layout", "spring")
    k = kwargs.get("k", 2.0)  # сила отталкивания для spring layout
    iterations = kwargs.get("iterations", 100)
    scale = kwargs.get("scale", 2.0)  # масштаб для circular layout

    if layout_algo == "spring":
        pos = nx.spring_layout(G, seed=42, k=k, iterations=iterations)
    elif layout_algo == "circular":
        pos = nx.circular_layout(G, scale=scale)
    elif layout_algo == "kamada_kawai":
        try:
            pos = nx.kamada_kawai_layout(G)
        except Exception:
            import sys
            print(f"Предупреждение: kamada_kawai layout недоступен (требуется scipy). Используется spring layout.", file=sys.stderr)
            pos = nx.spring_layout(G, seed=42, k=k, iterations=iterations)
    elif layout_algo == "planar":
        pos = nx.planar_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42, k=k, iterations=iterations)

    fig = Figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111)

    # Рисуем узлы
    for node_id, attrs in node_attrs.items():
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[node_id],
            node_color=[attrs["color"]],
            node_shape=attrs.get("shape", "s"),
            node_size=kwargs.get("node_size", 3000),
            ax=ax,
        )
        # Подписи узлов
        ax.text(
            pos[node_id][0],
            pos[node_id][1],
            attrs["label"],
            fontsize=kwargs.get("font_size", 10),
            color=attrs["text_color"],
            ha="center",
            va="center",
            wrap=True,
        )

    # Рисуем рёбра
    nx.draw_networkx_edges(
        G, pos,
        edge_color="#555555",
        width=1.5,
        arrows=True,
        arrowsize=15,
        ax=ax,
    )

    # Убираем оси
    ax.set_axis_off()
    fig.tight_layout()

    # Сохраняем в байты
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def render_graph_to_file(
    metadata: SQLMetadata,
    file_path: str,
    output_format: str = "png",
    **kwargs,
) -> str:
    """Генерирует граф и сохраняет его в файл.

    Args:
        metadata: Метаданные SQL запроса.
        file_path: Путь к файлу (без расширения, расширение добавится автоматически).
        output_format: Формат вывода (png, svg, pdf). Поддерживается только PNG.
        **kwargs: Дополнительные аргументы для render_graph_to_bytes.

    Returns:
        Полный путь к созданному файлу.
    """
    if not file_path.endswith(f".{output_format}"):
        file_path = f"{file_path}.{output_format}"

    image_data = render_graph_to_bytes(metadata, output_format=output_format, **kwargs)
    with open(file_path, "wb") as f:
        f.write(image_data)
    return file_path


if __name__ == "__main__":
    # Пример использования
    from core.sql_parser import ParserFactory

    sql = """
    SELECT
        u.id AS user_id,
        u.name,
        COUNT(o.order_id) as order_count
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    GROUP BY u.id, u.name
    """
    parser = ParserFactory.create_parser("sqlglot")
    metadata = parser.parse(sql)
    # Сохраняем граф в файл
    path = render_graph_to_file(metadata, "example_lineage")
    print(f"Граф сохранён в {path}")
    # Можно также получить байты
    # bytes_data = render_graph_to_bytes(metadata)