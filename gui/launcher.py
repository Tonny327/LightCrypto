"""
LightCrypto GUI - Стартовое окно
Выбор типа шифрования: LibSodium или Custom Codec
"""

import tkinter as tk
from tkinter import ttk
import re
from common.constants import *
from common.config import ConfigManager


class LauncherWindow:
    """
    Стартовое окно выбора типа шифрования
    """
    
    def __init__(self, config: ConfigManager, on_select):
        """
        Args:
            config: Менеджер конфигурации
            on_select: Callback при выборе типа (принимает 'libsodium' или 'custom')
        """
        self.config = config
        self.on_select = on_select
        
        self.root = tk.Tk()
        self.root.title("🔐 LightCrypto")
        self.root.geometry(f"{LAUNCHER_WIDTH}x{LAUNCHER_HEIGHT}")
        self.root.configure(bg=COLOR_BACKGROUND)
        self.root.resizable(False, False)
        
        # Центрирование окна
        self._center_window()
        
        self._create_widgets()
        
        # Загрузка сохраненной геометрии
        geom = config.get_window_geometry('launcher')
        if geom:
            self.root.geometry(f"{geom['width']}x{geom['height']}+{geom['x']}+{geom['y']}")
        
        # Сохранение при закрытии
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _center_window(self):
        """Центрирование окна на экране"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _create_widgets(self):
        """Создание элементов интерфейса"""
        # Заголовок
        title_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=80)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🔐 LightCrypto",
            font=('Arial', 20, 'bold'),
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        title_label.pack(expand=True)
        
        subtitle_label = tk.Label(
            title_frame,
            text="Система защищенной передачи данных",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_SECONDARY
        )
        subtitle_label.pack(expand=True)
        
        # Инструкция
        instruction = tk.Label(
            self.root,
            text="Выберите тип шифрования:",
            font=FONT_TITLE,
            bg=COLOR_BACKGROUND,
            fg=COLOR_TEXT_PRIMARY
        )
        instruction.pack(pady=(0, 20))
        
        # Кнопки выбора
        buttons_frame = tk.Frame(self.root, bg=COLOR_BACKGROUND)
        buttons_frame.pack(expand=True, pady=20)
        
        # Кнопка LibSodium
        libsodium_frame = self._create_choice_button(
            buttons_frame,
            emoji=EMOJI_LIBSODIUM,
            title="LibSodium",
            subtitle="ChaCha20-Poly1305",
            description="Промышленный\nстандарт",
            color=COLOR_LIBSODIUM,
            command=lambda: self._on_choice('libsodium')
        )
        libsodium_frame.grid(row=0, column=0, padx=20)
        
        # Кнопка Custom Codec
        custom_frame = self._create_choice_button(
            buttons_frame,
            emoji=EMOJI_CUSTOM,
            title="Custom Codec",
            subtitle="Digital Coding",
            description="Экспериментальный\nалгоритм",
            color=COLOR_CUSTOM,
            command=lambda: self._on_choice('custom')
        )
        custom_frame.grid(row=0, column=1, padx=20)
        
        # Версия
        version_label = tk.Label(
            self.root,
            text="v1.0.0",
            font=('Arial', 8),
            bg=COLOR_BACKGROUND,
            fg=COLOR_TEXT_SECONDARY
        )
        version_label.pack(side=tk.BOTTOM, anchor=tk.SE, padx=10, pady=5)
    
    def _create_choice_button(self, parent, emoji, title, subtitle, description, color, command):
        """Создание кнопки выбора типа шифрования"""
        frame = tk.Frame(
            parent,
            bg=color,
            width=200,
            height=180,
            relief=tk.RAISED,
            borderwidth=2
        )
        frame.pack_propagate(False)
        
        # Эмодзи
        emoji_label = tk.Label(
            frame,
            text=emoji,
            font=FONT_EMOJI_LARGE,
            bg=color
        )
        emoji_label.pack(pady=(10, 5))
        
        # Заголовок
        title_label = tk.Label(
            frame,
            text=title,
            font=('Arial', 14, 'bold'),
            bg=color,
            fg='white'
        )
        title_label.pack()
        
        # Подзаголовок
        subtitle_label = tk.Label(
            frame,
            text=subtitle,
            font=('Arial', 10),
            bg=color,
            fg='white'
        )
        subtitle_label.pack()
        
        # Описание
        desc_label = tk.Label(
            frame,
            text=description,
            font=('Arial', 9),
            bg=color,
            fg='white',
            justify=tk.CENTER
        )
        desc_label.pack(pady=5)
        
        # Кнопка
        button = tk.Button(
            frame,
            text="ВЫБРАТЬ",
            font=FONT_BUTTON,
            bg='white',
            fg=color,
            command=command,
            cursor='hand2',
            relief=tk.RAISED,
            borderwidth=2
        )
        button.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        # Эффекты при наведении
        def on_enter(e):
            frame.config(relief=tk.SUNKEN)
        
        def on_leave(e):
            frame.config(relief=tk.RAISED)
        
        frame.bind('<Enter>', on_enter)
        frame.bind('<Leave>', on_leave)
        
        # Клик по frame тоже вызывает команду
        for widget in [frame, emoji_label, title_label, subtitle_label, desc_label]:
            widget.bind('<Button-1>', lambda e: command())
        
        return frame
    
    def _on_choice(self, choice: str):
        """Обработка выбора типа шифрования"""
        self._save_geometry()
        self.root.destroy()
        self.on_select(choice)
    
    def _on_closing(self):
        """Обработка закрытия окна"""
        self._save_geometry()
        self.root.destroy()
    
    def _save_geometry(self):
        """Сохранение геометрии окна"""
        geom = self.root.geometry()
        # Формат: WIDTHxHEIGHT+X+Y
        match = re.match(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', geom)
        if match:
            width, height, x, y = map(int, match.groups())
            self.config.set_window_geometry('launcher', width, height, x, y)
    
    def run(self):
        """Запуск главного цикла окна"""
        self.root.mainloop()

