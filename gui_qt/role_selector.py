"""
LightCrypto GUI - Окно выбора роли (PyQt6)
Выбор между Encrypt (отправитель) и Decrypt (получатель)
"""

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from common.constants import *
from common.config import ConfigManager
from common.base_window import BaseWindow


class RoleSelectorWindow(BaseWindow):
    """
    Окно выбора роли: Encrypt или Decrypt
    """
    
    def __init__(self, config: ConfigManager, cipher_type: str, on_select, on_back):
        """
        Args:
            config: Менеджер конфигурации
            cipher_type: Тип шифрования ('libsodium' или 'custom')
            on_select: Callback при выборе роли (принимает 'encrypt' или 'decrypt')
            on_back: Callback для возврата назад
        """
        # Заголовок окна зависит от типа шифрования
        if cipher_type == 'custom':
            title = "🔐 LightCrypto - Custom Codec"
        else:
            title = "🔐 LightCrypto - Выбор роли"
        super().__init__(title, config)
        self.cipher_type = cipher_type
        self.on_select = on_select
        self.on_back_callback = on_back
        self.show_back_button = on_back is not None  # Показывать кнопку "Назад" только если есть callback
        
        self.setFixedSize(ROLE_SELECTOR_WIDTH, ROLE_SELECTOR_HEIGHT)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Создание элементов интерфейса"""
        # Заголовок с выбранным методом
        header_frame = QFrame()
        header_frame.setFixedHeight(60)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)
        
        cipher_name = "LibSodium" if self.cipher_type == 'libsodium' else "Custom Codec"
        cipher_emoji = EMOJI_LIBSODIUM if self.cipher_type == 'libsodium' else EMOJI_CUSTOM
        
        header_label = QLabel(f"Выбранный метод: {cipher_emoji} {cipher_name}")
        header_font = QFont('Arial', 14, QFont.Weight.Bold)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(header_label)
        
        self.main_layout.addWidget(header_frame)
        
        # Инструкция
        if os.name == 'nt':  # Windows - показываем локальный режим
            instruction = QLabel("Выберите режим работы:")
        else:
            instruction = QLabel("Выберите роль компьютера:")
        instruction_font = QFont('Arial', 14, QFont.Weight.Bold)
        instruction.setFont(instruction_font)
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(instruction)
        
        # Кнопки выбора роли
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        buttons_layout.setContentsMargins(15, 0, 15, 0)
        
        if os.name == 'nt':  # Windows - локальный режим
            # Кнопка "Локальное кодирование"
            local_encode_card = self._create_role_card(
                emoji='📤',
                title="Кодирование",
                subtitle="(Encode)",
                description="Локальный режим",
                color=COLOR_ENCRYPT_DARK,
                command=lambda: self._on_role_choice('local_encode')
            )
            buttons_layout.addWidget(local_encode_card)
            
            # Кнопка "Локальное декодирование"
            local_decode_card = self._create_role_card(
                emoji='📥',
                title="Декодирование",
                subtitle="(Decode)",
                description="Локальный режим",
                color=COLOR_DECRYPT_DARK,
                command=lambda: self._on_role_choice('local_decode')
            )
            buttons_layout.addWidget(local_decode_card)
        else:
            # Linux - сетевой режим
            # Кнопка Encrypt
            encrypt_card = self._create_role_card(
                emoji=EMOJI_ENCRYPT,
                title="Отправитель",
                subtitle="(Encrypt)",
                description="Компьютер A",
                color=COLOR_ENCRYPT_DARK,
                command=lambda: self._on_role_choice('encrypt')
            )
            buttons_layout.addWidget(encrypt_card)
            
            # Кнопка Decrypt
            decrypt_card = self._create_role_card(
                emoji=EMOJI_DECRYPT,
                title="Получатель",
                subtitle="(Decrypt)",
                description="Компьютер B",
                color=COLOR_DECRYPT_DARK,
                command=lambda: self._on_role_choice('decrypt')
            )
            buttons_layout.addWidget(decrypt_card)
        
        self.main_layout.addLayout(buttons_layout)
        self.main_layout.addStretch()
        
        # Кнопка "Назад" - показываем только если есть callback
        if self.show_back_button:
            back_button = QPushButton("← Назад")
            back_button.setFixedWidth(150)
            back_button.clicked.connect(self._on_back)
            back_button.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                }
            """)
            self.main_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)
    
    def _create_role_card(self, emoji, title, subtitle, description, color, command):
        """Создание карточки выбора роли"""
        card = QFrame()
        # Увеличиваем высоту карточки, чтобы кнопка не выходила за пределы
        card.setFixedSize(180, 160)
        # Убираем hover эффект с карточки - только кнопка будет подсвечиваться
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border: 2px solid {color};
                border-radius: 8px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        # Уменьшаем отступы, чтобы все поместилось
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(3)
        
        # Эмодзи (немного уменьшаем размер)
        emoji_label = QLabel(emoji)
        emoji_font = QFont('Arial', 40)
        emoji_label.setFont(emoji_font)
        emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(emoji_label)
        
        # Заголовок
        title_label = QLabel(title)
        title_font = QFont('Arial', 13, QFont.Weight.Bold)
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
        
        # Добавляем растяжку перед кнопкой, чтобы она была внизу
        card_layout.addStretch()
        
        # Кнопка с улучшенным hover эффектом
        button = QPushButton("ВЫБРАТЬ")
        button_font = QFont('Arial', 11, QFont.Weight.Bold)
        button.setFont(button_font)
        # Улучшенный стиль кнопки с более заметным hover эффектом
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: #0078d4;
                border: 2px solid white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 30px;
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
    
    def _on_role_choice(self, role: str):
        """Обработка выбора роли"""
        self.close()
        self.on_select(self.cipher_type, role)
    
    def _on_back(self):
        """Возврат к предыдущему окну"""
        self.close()
        self.on_back_callback()

