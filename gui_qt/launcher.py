"""
LightCrypto GUI - Стартовое окно (PyQt6)
Выбор типа шифрования: LibSodium или Custom Codec
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from common.constants import *
from common.config import ConfigManager
from common.base_window import BaseWindow


class LauncherWindow(BaseWindow):
    """
    Стартовое окно выбора типа шифрования
    """
    
    def __init__(self, config: ConfigManager, on_select):
        """
        Args:
            config: Менеджер конфигурации
            on_select: Callback при выборе типа (принимает 'libsodium' или 'custom')
        """
        super().__init__("🔐 LightCrypto", config)
        self.on_select = on_select
        
        self.setFixedSize(LAUNCHER_WIDTH, LAUNCHER_HEIGHT)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Создание элементов интерфейса"""
        # Заголовок
        title_frame = QFrame()
        title_frame.setFixedHeight(80)
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)
        
        title_label = QLabel("🔐 LightCrypto")
        title_font = QFont('Arial', 20, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Система защищенной передачи данных")
        subtitle_font = QFont('Arial', 10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY_DARK};")
        title_layout.addWidget(subtitle_label)
        
        self.main_layout.addWidget(title_frame)
        
        # Инструкция
        instruction = QLabel("Выберите тип шифрования:")
        instruction_font = QFont('Arial', 14, QFont.Weight.Bold)
        instruction.setFont(instruction_font)
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(instruction)
        
        # Кнопки выбора
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)
        buttons_layout.setContentsMargins(20, 0, 20, 0)
        
        # Кнопка LibSodium
        libsodium_card = self._create_choice_card(
            emoji=EMOJI_LIBSODIUM,
            title="LibSodium",
            subtitle="ChaCha20-Poly1305",
            description="Промышленный\nстандарт",
            color=COLOR_LIBSODIUM_DARK,
            command=lambda: self._on_choice('libsodium')
        )
        buttons_layout.addWidget(libsodium_card)
        
        # Кнопка Custom Codec
        custom_card = self._create_choice_card(
            emoji=EMOJI_CUSTOM,
            title="Custom Codec",
            subtitle="Digital Coding",
            description="Экспериментальный\nалгоритм",
            color=COLOR_CUSTOM_DARK,
            command=lambda: self._on_choice('custom')
        )
        buttons_layout.addWidget(custom_card)
        
        self.main_layout.addLayout(buttons_layout)
        self.main_layout.addStretch()
        
        # Версия
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY_DARK}; font-size: 8pt;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.main_layout.addWidget(version_label)
    
    def _create_choice_card(self, emoji, title, subtitle, description, color, command):
        """Создание карточки выбора типа шифрования"""
        card = QFrame()
        card.setFixedSize(200, 180)
        # Убираем hover эффект с карточки - только кнопка будет подсвечиваться
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border: 2px solid {color};
                border-radius: 8px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(5)
        
        # Эмодзи
        emoji_label = QLabel(emoji)
        emoji_font = QFont('Arial', 48)
        emoji_label.setFont(emoji_font)
        emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(emoji_label)
        
        # Заголовок
        title_label = QLabel(title)
        title_font = QFont('Arial', 14, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: white;")
        card_layout.addWidget(title_label)
        
        # Подзаголовок
        subtitle_label = QLabel(subtitle)
        subtitle_font = QFont('Arial', 10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: white;")
        card_layout.addWidget(subtitle_label)
        
        # Описание
        desc_label = QLabel(description)
        desc_font = QFont('Arial', 9)
        desc_label.setFont(desc_font)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: white;")
        card_layout.addWidget(desc_label)
        
        # Кнопка с улучшенным hover эффектом
        button = QPushButton("ВЫБРАТЬ")
        button_font = QFont('Arial', 11, QFont.Weight.Bold)
        button.setFont(button_font)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: #0078d4;
                border: 2px solid white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #f0f0f0;
                border: 2px solid {COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: #e0e0e0;
                border: 2px solid {COLOR_ACCENT_PRESSED};
            }}
        """)
        button.clicked.connect(command)
        card_layout.addWidget(button)
        
        # Клик по карточке тоже вызывает команду
        card.mousePressEvent = lambda e: command()
        
        return card
    
    def _on_choice(self, choice: str):
        """Обработка выбора типа шифрования"""
        self._save_geometry()
        self.close()
        self.on_select(choice)

