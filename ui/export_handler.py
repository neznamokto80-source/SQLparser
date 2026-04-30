"""
Обработчик экспорта данных для SQL Metadata Parser.

Содержит логику экспорта данных в различные форматы,
включая диалоги сохранения файлов и обработку результатов.
"""
import os
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.export_manager import ExportManager

if TYPE_CHECKING:
    from models.sql_metadata import SQLMetadata
    from PyQt6.QtWidgets import QWidget, QStatusBar


class ExportHandler:
    """Класс для обработки экспорта данных в различные форматы."""
    
    def __init__(self, parent_widget: 'QWidget', status_bar: 'QStatusBar'):
        """Инициализирует обработчик экспорта.
        
        Args:
            parent_widget: Родительский виджет для диалогов
            status_bar: Статусная строка для отображения сообщений
        """
        self.parent = parent_widget
        self.status_bar = status_bar
        self.export_manager = ExportManager()
    
    def export_data(self, metadata: 'SQLMetadata', fmt: str) -> bool:
        """Экспортирует результаты анализа в файл указанного формата.
        
        Args:
            metadata: Объект SQLMetadata с данными для экспорта
            fmt: Строка идентификатора формата ("csv", "excel", "text", "json")
            
        Returns:
            bool: True если экспорт успешен, False в противном случае
        """
        if not metadata:
            QMessageBox.warning(self.parent, "Внимание", "Нет данных для экспорта.")
            return False
        
        # Определяем фильтры для файлового диалога
        filters = {
            "csv": "CSV файлы (*.csv);;Все файлы (*.*)",
            "excel": "Excel файлы (*.xlsx);;Excel 97-2003 (*.xls);;Все файлы (*.*)",
            "text": "Текстовые файлы (*.txt);;Все файлы (*.*)",
            "json": "JSON файлы (*.json);;Все файлы (*.*)"
        }
        
        file_filter = filters.get(fmt, "Все файлы (*.*)")
        
        # Определяем расширение файла по умолчанию
        default_extensions = {
            "csv": "csv",
            "excel": "xlsx",
            "text": "txt",
            "json": "json"
        }
        default_ext = default_extensions.get(fmt, fmt)
        
        path, _ = QFileDialog.getSaveFileName(
            self.parent,
            f"Экспорт в {fmt.upper()}",
            f"sql_metadata_export.{default_ext}",
            file_filter
        )
        
        if not path:
            return False
        
        try:
            ok = self.export_manager.export(metadata, path, strategy_name=fmt)
            if ok:
                self.status_bar.showMessage(f"Данные экспортированы в {fmt.upper()}: {os.path.basename(path)}")
                
                # Предложить открыть файл
                reply = QMessageBox.question(
                    self.parent,
                    "Успех",
                    f"Файл успешно создан!\n\n"
                    f"Всего строк: {len(metadata.column_analysis)}\n"
                    f"Уникальных таблиц: {len(metadata.get_unique_tables())}\n\n"
                    f"Открыть файл сейчас?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(path)
                return True
            else:
                QMessageBox.critical(self.parent, "Ошибка", "Не удалось экспортировать данные")
                return False
                
        except Exception as e:
            QMessageBox.critical(self.parent, "Ошибка", f"Не удалось экспортировать данные:\n{str(e)}")
            return False
    
    @staticmethod
    def get_format_filters() -> dict[str, str]:
        """Возвращает словарь фильтров для файловых диалогов по форматам.
        
        Returns:
            dict: Словарь форматов и соответствующих фильтров
        """
        return {
            "csv": "CSV файлы (*.csv);;Все файлы (*.*)",
            "excel": "Excel файлы (*.xlsx);;Excel 97-2003 (*.xls);;Все файлы (*.*)",
            "text": "Текстовые файлы (*.txt);;Все файлы (*.*)",
            "json": "JSON файлы (*.json);;Все файлы (*.*)"
        }
    
    @staticmethod
    def get_default_extension(fmt: str) -> str:
        """Возвращает расширение файла по умолчанию для указанного формата.
        
        Args:
            fmt: Строка идентификатора формата
            
        Returns:
            str: Расширение файла (без точки)
        """
        default_extensions = {
            "csv": "csv",
            "excel": "xlsx",
            "text": "txt",
            "json": "json"
        }
        return default_extensions.get(fmt, fmt)