"""
LightCrypto GUI - Стили QStyleSheet для PyQt6
Темная тема с современным дизайном
"""

from .constants import *


# Полный стиль темной темы
DARK_THEME = f"""
    /* Главное окно */
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
    }}
    
    /* Виджеты общего назначения */
    QWidget {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
    }}
    
    /* Кнопки */
    QPushButton {{
        background-color: {COLOR_ACCENT};
        color: white;
        border: none;
        padding: 6px 14px;
        border-radius: 4px;
        font-size: 9pt;
        font-weight: 600;
        min-height: 24px;
    }}
    
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_HOVER};
    }}
    
    QPushButton:pressed {{
        background-color: {COLOR_ACCENT_PRESSED};
    }}
    
    QPushButton:disabled {{
        background-color: {COLOR_BORDER_DARK};
        color: {COLOR_TEXT_SECONDARY_DARK};
    }}
    
    /* Кнопки успеха */
    QPushButton[class="success"] {{
        background-color: {COLOR_SUCCESS_DARK};
    }}
    
    QPushButton[class="success"]:hover {{
        background-color: #5dd4c0;
    }}
    
    /* Кнопки ошибки */
    QPushButton[class="error"] {{
        background-color: {COLOR_ERROR_DARK};
    }}
    
    QPushButton[class="error"]:hover {{
        background-color: #f69d8a;
    }}
    
    /* Кнопки предупреждения */
    QPushButton[class="warning"] {{
        background-color: {COLOR_WARNING_DARK};
        color: {COLOR_BACKGROUND_DARK};
    }}
    
    QPushButton[class="warning"]:hover {{
        background-color: #e6d699;
    }}
    
    /* Поля ввода */
    QLineEdit {{
        background-color: {COLOR_PANEL_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
        border: 2px solid {COLOR_BORDER_DARK};
        padding: 5px 8px;
        border-radius: 4px;
        font-size: 9pt;
        selection-background-color: {COLOR_ACCENT};
        selection-color: white;
    }}
    
    /* SpinBox и DoubleSpinBox без стрелок */
    QSpinBox, QDoubleSpinBox {{
        background-color: {COLOR_PANEL_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
        border: 2px solid {COLOR_BORDER_DARK};
        padding: 5px 8px;
        border-radius: 4px;
        font-size: 9pt;
        selection-background-color: {COLOR_ACCENT};
        selection-color: white;
    }}
    
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {COLOR_ACCENT};
    }}
    
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background-color: {COLOR_BORDER_DARK};
        color: {COLOR_TEXT_SECONDARY_DARK};
    }}
    
    /* Скрываем стрелки в SpinBox */
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        width: 0px;
        height: 0px;
    }}
    
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 0px;
        height: 0px;
    }}
    
    /* Выпадающие списки */
    QComboBox {{
        background-color: {COLOR_PANEL_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
        border: 2px solid {COLOR_BORDER_DARK};
        padding: 5px 8px;
        border-radius: 4px;
        font-size: 9pt;
        min-width: 100px;
    }}
    
    QComboBox:hover {{
        border: 2px solid {COLOR_ACCENT};
    }}
    
    QComboBox:focus {{
        border: 2px solid {COLOR_ACCENT};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 30px;
    }}
    
    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {COLOR_TEXT_PRIMARY_DARK};
        width: 0;
        height: 0;
        margin-right: 10px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {COLOR_PANEL_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
        border: 1px solid {COLOR_BORDER_DARK};
        selection-background-color: {COLOR_ACCENT};
        selection-color: white;
    }}
    
    /* Чекбоксы и радиокнопки */
    QCheckBox, QRadioButton {{
        color: {COLOR_TEXT_PRIMARY_DARK};
        font-size: 9pt;
        spacing: 6px;
    }}
    
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {COLOR_BORDER_DARK};
        border-radius: 3px;
        background-color: {COLOR_PANEL_DARK};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {COLOR_ACCENT};
        border-color: {COLOR_ACCENT};
        image: none;
    }}
    
    QRadioButton::indicator {{
        border-radius: 9px;
    }}
    
    QRadioButton::indicator:checked {{
        background-color: {COLOR_ACCENT};
        border-color: {COLOR_ACCENT};
    }}
    
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {COLOR_ACCENT};
    }}
    
    /* Группы (панели) */
    QGroupBox {{
        background-color: {COLOR_PANEL_DARK};
        border: 1px solid {COLOR_BORDER_DARK};
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 15px;
        font-size: 12pt;
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY_DARK};
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        color: {COLOR_TEXT_PRIMARY_DARK};
    }}
    
    /* Метки */
    QLabel {{
        color: {COLOR_TEXT_PRIMARY_DARK};
        font-size: 10pt;
    }}
    
    /* Терминал (текстовое поле) */
    QPlainTextEdit, QTextEdit {{
        background-color: #0d1117;
        color: #c9d1d9;
        border: 1px solid {COLOR_BORDER_DARK};
        border-radius: 6px;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 10pt;
        selection-background-color: {COLOR_ACCENT};
        selection-color: white;
    }}
    
    /* Скроллбары */
    QScrollBar:vertical {{
        background-color: {COLOR_BACKGROUND_DARK};
        width: 12px;
        border: none;
        margin: 0;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {COLOR_BORDER_DARK};
        border-radius: 6px;
        min-height: 20px;
        margin: 2px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {COLOR_PANEL_HOVER_DARK};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    
    QScrollBar:horizontal {{
        background-color: {COLOR_BACKGROUND_DARK};
        height: 12px;
        border: none;
        margin: 0;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {COLOR_BORDER_DARK};
        border-radius: 6px;
        min-width: 20px;
        margin: 2px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {COLOR_PANEL_HOVER_DARK};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    
    /* Область прокрутки */
    QScrollArea {{
        background-color: {COLOR_BACKGROUND_DARK};
        border: none;
    }}
    
    QScrollArea > QWidget > QWidget {{
        background-color: {COLOR_BACKGROUND_DARK};
    }}
    
    /* Фреймы */
    QFrame {{
        background-color: {COLOR_PANEL_DARK};
        border: 1px solid {COLOR_BORDER_DARK};
        border-radius: 6px;
    }}
    
    /* Диалоги */
    QDialog {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
    }}
    
    /* Табы (если используются) */
    QTabWidget::pane {{
        background-color: {COLOR_PANEL_DARK};
        border: 1px solid {COLOR_BORDER_DARK};
        border-radius: 4px;
    }}
    
    QTabBar::tab {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_SECONDARY_DARK};
        border: 1px solid {COLOR_BORDER_DARK};
        padding: 8px 16px;
        margin-right: 2px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {COLOR_PANEL_DARK};
        color: {COLOR_TEXT_PRIMARY_DARK};
        border-bottom: 2px solid {COLOR_ACCENT};
    }}
    
    QTabBar::tab:hover {{
        background-color: {COLOR_PANEL_HOVER_DARK};
    }}
"""

