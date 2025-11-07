"""
LightCrypto GUI - Окно выбора роли
Выбор между Encrypt (отправитель) и Decrypt (получатель)
"""

import tkinter as tk
from common.constants import *
from common.config import ConfigManager


class RoleSelectorWindow:
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
        self.config = config
        self.cipher_type = cipher_type
        self.on_select = on_select
        self.on_back_callback = on_back
        
        self.root = tk.Tk()
        self.root.title(f"🔐 LightCrypto - Выбор роли")
        self.root.geometry(f"{ROLE_SELECTOR_WIDTH}x{ROLE_SELECTOR_HEIGHT}")
        self.root.configure(bg=COLOR_BACKGROUND)
        self.root.resizable(False, False)
        
        # Центрирование окна
        self._center_window()
        
        self._create_widgets()
        
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
        # Заголовок с выбранным методом
        header_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=60)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)
        
        cipher_name = "LibSodium" if self.cipher_type == 'libsodium' else "Custom Codec"
        cipher_emoji = EMOJI_LIBSODIUM if self.cipher_type == 'libsodium' else EMOJI_CUSTOM
        
        header_label = tk.Label(
            header_frame,
            text=f"Выбранный метод: {cipher_emoji} {cipher_name}",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        header_label.pack(expand=True)
        
        # Инструкция
        instruction = tk.Label(
            self.root,
            text="Выберите роль компьютера:",
            font=FONT_TITLE,
            bg=COLOR_BACKGROUND,
            fg=COLOR_TEXT_PRIMARY
        )
        instruction.pack(pady=(0, 20))
        
        # Кнопки выбора роли
        buttons_frame = tk.Frame(self.root, bg=COLOR_BACKGROUND)
        buttons_frame.pack(expand=True, pady=10)
        
        # Кнопка Encrypt
        encrypt_frame = self._create_role_button(
            buttons_frame,
            emoji=EMOJI_ENCRYPT,
            title="Отправитель",
            subtitle="(Encrypt)",
            description="Компьютер A",
            color=COLOR_ENCRYPT,
            command=lambda: self._on_role_choice('encrypt')
        )
        encrypt_frame.grid(row=0, column=0, padx=15)
        
        # Кнопка Decrypt
        decrypt_frame = self._create_role_button(
            buttons_frame,
            emoji=EMOJI_DECRYPT,
            title="Получатель",
            subtitle="(Decrypt)",
            description="Компьютер B",
            color=COLOR_DECRYPT,
            command=lambda: self._on_role_choice('decrypt')
        )
        decrypt_frame.grid(row=0, column=1, padx=15)
        
        # Кнопка "Назад"
        back_button = tk.Button(
            self.root,
            text="← Назад",
            font=FONT_BUTTON,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            command=self._on_back,
            cursor='hand2',
            width=15
        )
        back_button.pack(pady=(10, 10))
    
    def _create_role_button(self, parent, emoji, title, subtitle, description, color, command):
        """Создание кнопки выбора роли"""
        frame = tk.Frame(
            parent,
            bg=color,
            width=180,
            height=140,
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
            font=('Arial', 13, 'bold'),
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
            fg='white'
        )
        desc_label.pack(pady=2)
        
        # Кнопка
        button = tk.Button(
            frame,
            text="ВЫБРАТЬ",
            font=FONT_BUTTON,
            bg='white',
            fg=color,
            command=command,
            cursor='hand2'
        )
        button.pack(pady=(5, 10), padx=15, fill=tk.X)
        
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
    
    def _on_role_choice(self, role: str):
        """Обработка выбора роли"""
        self.root.destroy()
        self.on_select(self.cipher_type, role)
    
    def _on_back(self):
        """Возврат к предыдущему окну"""
        self.root.destroy()
        self.on_back_callback()
    
    def _on_closing(self):
        """Обработка закрытия окна"""
        self.root.destroy()
    
    def run(self):
        """Запуск главного цикла окна"""
        self.root.mainloop()

