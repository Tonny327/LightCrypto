"""
LightCrypto GUI - Базовый класс для всех окон (PyQt6)
"""

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QScreen, QFont

from .styles import DARK_THEME
from .constants import *
from .config import ConfigManager


class BaseWindow(QMainWindow):
    """
    Базовый класс для всех окон приложения
    Предоставляет общую функциональность: стили, геометрию, центрирование
    """
    
    def __init__(self, title: str, config: ConfigManager, parent=None):
        """
        Args:
            title: Заголовок окна
            config: Менеджер конфигурации
            parent: Родительское окно
        """
        super().__init__(parent)
        self.config = config
        # Создаем безопасное имя окна для сохранения геометрии
        self.window_name = title.lower().replace(' ', '_').replace('🔐', '').replace('⚡', '').replace('📤', '').replace('📥', '').strip('_')
        
        self.setWindowTitle(title)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Применение темной темы
        self._apply_styles()
        
        # Загрузка сохраненной геометрии
        self._load_geometry()
    
    def _apply_styles(self):
        """Применение темной темы к окну"""
        self.setStyleSheet(DARK_THEME)
    
    def _load_geometry(self):
        """Загрузка сохраненной геометрии окна"""
        geom = self.config.get_window_geometry(self.window_name)
        if geom and 'width' in geom and 'height' in geom:
            width = geom.get('width', WINDOW_DEFAULT_WIDTH)
            height = geom.get('height', WINDOW_DEFAULT_HEIGHT)
            x = geom.get('x', -1)
            y = geom.get('y', -1)
            
            if x >= 0 and y >= 0:
                self.setGeometry(x, y, width, height)
            else:
                # Центрирование если позиция не сохранена
                self.resize(width, height)
                self._center_window()
        else:
            # Первый запуск - центрирование
            self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
            self._center_window()
    
    def _center_window(self):
        """Центрирование окна на экране"""
        screen = self.screen()
        if screen:
            screen_geometry = screen.geometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())
    
    def _save_geometry(self):
        """Сохранение геометрии окна"""
        geometry = self.geometry()
        self.config.set_window_geometry(
            self.window_name,
            geometry.width(),
            geometry.height(),
            geometry.x(),
            geometry.y()
        )
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self._save_geometry()
        self.config.save()
        super().closeEvent(event)

