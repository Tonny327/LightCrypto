"""
LightCrypto GUI - Custom Codec Encrypt (Отправитель)
"""

import tkinter as tk
from tkinter import messagebox

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.constants import *
from common.config import ConfigManager
from libsodium.encrypt_window import LibSodiumEncryptGUI
from custom.codec_panel import CodecPanel


class CustomCodecEncryptGUI(LibSodiumEncryptGUI):
    """
    GUI для Custom Digital Codec шифрования (Отправитель)
    Наследует LibSodium GUI и добавляет панель параметров кодека
    """
    
    def __init__(self, config: ConfigManager, on_back):
        # Изменяем заголовок окна перед вызовом родителя
        self._window_title = "🔐 LightCrypto - Custom Codec Encrypt (Отправитель)"
        self.codec_panel = None
        super().__init__(config, on_back)
    
    def _create_widgets(self):
        """Создание всех элементов интерфейса"""
        # Основной контейнер с прокруткой
        main_canvas = tk.Canvas(self.root, bg=COLOR_BACKGROUND, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas, bg=COLOR_BACKGROUND)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Поддержка прокрутки колесиком мыши
        self._bind_mouse_wheel(main_canvas, scrollable_frame)
        
        # ВАЖНО: Сначала панель параметров кодека
        self.codec_panel = CodecPanel(scrollable_frame, self.config, self.terminal)
        self.codec_panel.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Затем остальные панели
        self._create_tap_panel(scrollable_frame)
        self._create_network_panel(scrollable_frame)
        self._create_control_panel(scrollable_frame)
        self._create_terminal_panel(scrollable_frame)
        self._create_utils_panel(scrollable_frame)
        
        # Размещение
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Обновляем заголовок окна
        self.root.title(self._window_title)
    
    def _start_encryption(self):
        """Запуск шифрования с параметрами кодека"""
        # Валидация параметров кодека
        if not self.codec_panel.is_valid():
            messagebox.showerror(
                "Ошибка",
                "Некорректные параметры кодека!\n"
                "Проверьте выбор CSV и значения M, Q."
            )
            return
        
        # Валидация сети
        ip = self.ip_var.get().strip()
        port_str = self.port_var.get().strip()
        
        if not validate_ip(ip):
            messagebox.showerror("Ошибка", "Некорректный IP-адрес!")
            return
        
        try:
            port = int(port_str)
            if not validate_port(port):
                raise ValueError()
        except:
            messagebox.showerror("Ошибка", f"Некорректный порт! Допустимый диапазон: {PORT_MIN}-{PORT_MAX}")
            return
        
        # Получение параметров кодека
        params = self.codec_panel.get_params()
        
        if not params['csv_path']:
            messagebox.showerror("Ошибка", "CSV файл не выбран!")
            return
        
        # Сохранение параметров
        self.config.set_custom_encrypt_ip(ip)
        self.config.set_custom_port(port)
        self.config.set_custom_msg_mode(self.msg_mode_var.get())
        self.codec_panel.save_to_config()
        self.config.save()
        
        # Формирование команды
        cmd = [
            'sudo', TAP_ENCRYPT,
            '--codec', params['csv_path'],
            '--M', str(params['M']),
            '--Q', str(params['Q']),
            '--fun', str(params['funType']),
            '--h1', str(params['h1']),
            '--h2', str(params['h2'])
        ]
        
        if self.msg_mode_var.get():
            cmd.append('--msg')
        
        cmd.append(ip)
        cmd.append(str(port))
        
        # Вывод команды
        from common.utils import format_command_list
        self.terminal.print_to_terminal(
            f"{EMOJI_INFO} Команда: {format_command_list(cmd)}",
            'info'
        )
        
        # Запуск
        self.terminal.run_process(cmd, use_xterm=False)
        
        # Показать поле ввода если режим сообщений
        if self.msg_mode_var.get():
            self.terminal.show_input_field(True)
        
        # Обновление кнопки
        self.start_button.config(
            text=f"{EMOJI_STOP} ОСТАНОВИТЬ ШИФРОВАНИЕ",
            bg=COLOR_ERROR
        )


# Импорт для валидации
from common.utils import validate_ip, validate_port
from tkinter import ttk

