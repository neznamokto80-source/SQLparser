"""
Диалог справки для SQL Metadata Parser.

Содержит стилизованное окно справки с поддержкой темной и светлой тем.
"""
from PyQt6.QtWidgets import QMessageBox

from ui.help_text import HELP_TEXT


class HelpDialog:
    """Класс для отображения диалога справки."""
    
    @staticmethod
    def show(parent, is_dark_theme: bool) -> None:
        """Отображает окно справки.
        
        Args:
            parent: Родительский виджет
            is_dark_theme: Флаг темной темы
        """
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle("Справка")
        msg_box.setText(HELP_TEXT)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        # Применяем стиль в зависимости от темы
        if is_dark_theme:
            HelpDialog._apply_dark_theme(msg_box)
        else:
            HelpDialog._apply_light_theme(msg_box)
        
        msg_box.exec()
    
    @staticmethod
    def _apply_dark_theme(msg_box: QMessageBox) -> None:
        """Применяет стиль для тёмной темы.
        
        Args:
            msg_box: Диалоговое окно для стилизации
        """
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                background-color: #555555;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QMessageBox QPushButton:hover {
                background-color: #666666;
                border-color: #007acc;
            }
        """)
    
    @staticmethod
    def _apply_light_theme(msg_box: QMessageBox) -> None:
        """Применяет стиль для светлой темы.
        
        Args:
            msg_box: Диалоговое окно для стилизации
        """
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f5f7fa;
                color: #2c3e50;
            }
            QMessageBox QLabel {
                color: #2c3e50;
            }
            QMessageBox QPushButton {
                background-color: #f8fafc;
                color: #2c3e50;
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QMessageBox QPushButton:hover {
                background-color: #e8f4fc;
                border-color: #3498db;
            }
        """)
    
    @staticmethod
    def get_dark_theme_stylesheet() -> str:
        """Возвращает строку стилей для тёмной темы.
        
        Returns:
            str: CSS стили для тёмной темы
        """
        return """
            QMessageBox {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                background-color: #555555;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QMessageBox QPushButton:hover {
                background-color: #666666;
                border-color: #007acc;
            }
        """
    
    @staticmethod
    def get_light_theme_stylesheet() -> str:
        """Возвращает строку стилей для светлой темы.
        
        Returns:
            str: CSS стили для светлой темы
        """
        return """
            QMessageBox {
                background-color: #f5f7fa;
                color: #2c3e50;
            }
            QMessageBox QLabel {
                color: #2c3e50;
            }
            QMessageBox QPushButton {
                background-color: #f8fafc;
                color: #2c3e50;
                border: 1px solid #d1d9e6;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QMessageBox QPushButton:hover {
                background-color: #e8f4fc;
                border-color: #3498db;
            }
        """