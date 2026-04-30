"""
Презентация данных для SQL Metadata Parser.

Содержит логику отображения данных в UI элементах,
устраняя дублирование кода между различными методами.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QTreeWidgetItem

if TYPE_CHECKING:
    from models.sql_metadata import SQLMetadata
    from PyQt6.QtWidgets import QTreeWidget, QTextEdit


class DataPresenter:
    """Класс для презентации данных SQL метаданных в UI элементах."""
    
    @staticmethod
    def extract_table_info(table_name: str, metadata: 'SQLMetadata') -> tuple[str, str, str]:
        """Извлекает схему, имя таблицы и тип объекта из полного имени таблицы.
        
        Args:
            table_name: Полное имя таблицы (может содержать схему)
            metadata: Объект SQLMetadata для поиска дополнительной информации
            
        Returns:
            tuple: (schema, table_name_without_schema, object_type)
        """
        schema = ""
        table_name_without_schema = table_name or ""
        object_type = ""
        
        if table_name:
            if "." in table_name:
                parts = table_name.split(".", 1)
                schema = parts[0]
                table_name_without_schema = parts[1]
            
            # Ищем таблицу в метаданных (сначала по схеме, если нет - по имени)
            found_table = None
            if schema:
                found_table = metadata.get_table_by_name(table_name_without_schema, schema)
            if not found_table:
                # Поиск по имени без схемы (первая подходящая)
                for t in metadata.get_unique_tables():
                    if t.name == table_name_without_schema:
                        found_table = t
                        break
            
            if found_table:
                object_type = found_table.table_type.value
                # Если схема не была извлечена из table, возьмём из found_table
                if not schema:
                    schema = found_table.schema or ""
        
        return schema, table_name_without_schema, object_type
    
    @staticmethod
    def populate_columns_tree(columns_tree: 'QTreeWidget', metadata: 'SQLMetadata') -> None:
        """Заполняет дерево колонок данными из метаданных.
        
        Args:
            columns_tree: Дерево для отображения колонок
            metadata: Объект SQLMetadata с данными
        """
        columns_tree.clear()
        
        for col in metadata.column_analysis:
            column_row = QTreeWidgetItem(columns_tree)
            column_row.setText(0, col.column_name or "")          # Колонка
            column_row.setText(1, col.full_name or "")            # Полное имя колонки
            
            # Извлекаем схему, имя таблицы и тип объекта
            schema, table_name, object_type = DataPresenter.extract_table_info(col.table or "", metadata)
            
            column_row.setText(2, schema)                         # Схема
            column_row.setText(3, table_name)                     # Таблица
            column_row.setText(4, col.table_alias or "")          # Алиас таблицы
            column_row.setText(5, object_type)                    # Тип объекта
            column_row.setText(6, col.get_aliases_str())          # Алиасы
            
            # Фильтруем "calculation" из usage_locations
            filtered_locations = [loc for loc in col.usage_locations if loc.lower() != "calculation"]
            column_row.setText(7, ", ".join(filtered_locations))  # Где используется
            column_row.setText(8, str(col.usage_count))           # Количество упоминаний
    
    @staticmethod
    def populate_tables_tree(tables_tree: 'QTreeWidget', metadata: 'SQLMetadata') -> None:
        """Заполняет дерево таблиц данными из метаданных.
        
        Args:
            tables_tree: Дерево для отображения таблиц
            metadata: Объект SQLMetadata с данными
        """
        tables_tree.clear()
        
        for table in metadata.get_unique_tables():
            item = QTreeWidgetItem(tables_tree)
            item.setText(0, table.schema or "")
            item.setText(1, table.name)
            item.setText(2, table.get_aliases_str())
            item.setText(3, table.table_type.value)
            item.setText(4, str(len(table.columns)))
            item.setText(5, table.join_type or "")
    
    @staticmethod
    def populate_lineage_tree(lineage_tree: 'QTreeWidget', metadata: 'SQLMetadata') -> None:
        """Заполняет дерево линеджа данными из метаданных.
        
        Args:
            lineage_tree: Дерево для отображения линеджа
            metadata: Объект SQLMetadata с данными
        """
        lineage_tree.clear()
        
        for col in metadata.column_analysis:
            lineage_row = QTreeWidgetItem(lineage_tree)
            lineage_row.setText(0, col.column_name)
            lineage_row.setText(1, col.table or "")
            lineage_row.setText(2, col.full_name or "")
            lineage_row.setText(3, ", ".join(col.dependencies))
            
            # Фильтруем "calculation" из usage_locations
            filtered_locations = [loc for loc in col.usage_locations if loc.lower() != "calculation"]
            lineage_row.setText(4, ", ".join(filtered_locations))
    
    @staticmethod
    def populate_stats_text(stats_text: 'QTextEdit', metadata: 'SQLMetadata') -> None:
        """Заполняет текстовое поле статистики данными из метаданных.
        
        Args:
            stats_text: Текстовое поле для отображения статистики
            metadata: Объект SQLMetadata с данными
        """
        stats = metadata.get_statistics()
        lines = [
            "SQL Metadata Parser v4.0",
            "",
            f"Всего колонок: {stats.get('total_columns', 0)}",
            f"Всего таблиц: {stats.get('total_tables', 0)}",
            f"Уникальных таблиц: {stats.get('unique_tables', 0)}",
            f"Колонок в вычислениях: {stats.get('calculation_columns', 0)}",
            f"Всего упоминаний колонок: {stats.get('total_column_mentions', 0)}",
            "",
            "Пример вывода таблицы 'Колонки':",
            metadata.sample_columns_output,
        ]
        stats_text.setPlainText("\n".join(lines))
    
    @staticmethod
    def generate_text_output(metadata: 'SQLMetadata', dialect_value: str) -> str:
        """Генерирует текстовый вывод результатов парсинга.
        
        Args:
            metadata: Объект SQLMetadata с данными
            dialect_value: Значение диалекта SQL для отображения
            
        Returns:
            str: Отформатированный текстовый вывод
        """
        text = f"=== РЕЗУЛЬТАТЫ ПАРСИНГА SQL ===\n"
        text += f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += f"Диалект SQL: {dialect_value}\n\n"
        
        # Уникальные таблицы
        text += "=== УНИКАЛЬНЫЕ ТАБЛИЦЫ ===\n"
        for i, table in enumerate(metadata.get_unique_tables(), 1):
            aliases_info = f" (алиасы: {table.get_aliases_str()})" if table.aliases else ""
            text += f"{i}. {table.schema or ''}.{table.name}{aliases_info} - {table.table_type.value}\n"
        text += f"\nВсего уникальных таблиц: {len(metadata.get_unique_tables())}\n\n"
        
        # Детальная информация
        text += "=== ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ===\n\n"
        for i, col in enumerate(metadata.column_analysis, 1):
            text += f"{i}. Колонка: {col.column_name}\n"
            text += f"   Таблица: {col.table or ''} "
            text += f"(Алиас: {col.table_alias or ''})\n"
            text += f"   Полное имя: {col.full_name or ''}\n"
            text += f"   Вычисление: {col.calculation_type or 'нет'}\n"
            # Фильтруем "calculation" из usage_locations
            filtered_locations = [loc for loc in col.usage_locations if loc.lower() != "calculation"]
            text += f"   Использование: {', '.join(filtered_locations) if filtered_locations else 'нет'}\n"
            text += f"{'-'*40}\n"
        
        return text
    
    @staticmethod
    def generate_clipboard_text(metadata: 'SQLMetadata') -> str:
        """Генерирует текст для копирования в буфер обмена в формате TSV.
        
        Args:
            metadata: Объект SQLMetadata с данными
            
        Returns:
            str: Текст в формате TSV для буфера обмена
        """
        rows = ["Колонка\tПолное имя\tСхема\tТаблица\tАлиас таблицы\tТип объекта\tАлиасы\tГде используется\tКоличество упоминаний"]
        
        for col in metadata.column_analysis:
            # Извлекаем схему, имя таблицы и тип объекта
            schema, table_name, object_type = DataPresenter.extract_table_info(col.table or "", metadata)
            
            rows.append(
                f"{col.column_name or ''}\t"
                f"{col.full_name or ''}\t"
                f"{schema}\t"
                f"{table_name}\t"
                f"{col.table_alias or ''}\t"
                f"{object_type}\t"
                f"{col.get_aliases_str()}\t"
                f"{', '.join(col.usage_locations)}\t"
                f"{col.usage_count}"
            )
        
        return "\n".join(rows)