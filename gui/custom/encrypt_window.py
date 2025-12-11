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
from common.terminal import EmbeddedTerminal
from libsodium.encrypt_window import LibSodiumEncryptGUI
from custom.codec_panel import CodecPanel
from tkinter import filedialog
import os


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
        
        # ВАЖНО: Сначала панель параметров кодека
        self.codec_panel = CodecPanel(scrollable_frame, self.config, self.terminal)
        self.codec_panel.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Переменные для локального режима (инициализируем ДО создания панелей)
        self.local_output_path_var = tk.StringVar(value='')
        
        # Создаем переключатель режимов (сетевой/локальный)
        self._create_mode_switch(scrollable_frame)
        
        # Затем остальные панели (в правильном порядке)
        self._create_tap_panel(scrollable_frame)
        self._create_network_panel(scrollable_frame)
        # Локальные элементы создаем перед терминалом (как в PyQt6)
        self._create_local_file_panel(scrollable_frame)
        self._create_local_start_button(scrollable_frame)
        self._create_terminal_panel(scrollable_frame)
        self._create_utils_panel(scrollable_frame)
        
        # Инициализация видимости панелей
        self.local_file_frame.pack_forget()  # Скрываем по умолчанию (сетевой режим)
        self.local_start_button_frame.pack_forget()  # Скрываем по умолчанию
        self._on_mode_changed()
        
        # Размещение
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Поддержка прокрутки колесиком мыши (ПОСЛЕ создания всех виджетов)
        self._bind_mouse_wheel(main_canvas, scrollable_frame)
        
        # Обновляем заголовок окна
        self.root.title(self._window_title)
    
    def _create_mode_switch(self, parent):
        """Создает переключатель между сетевым и локальным режимом"""
        switch_frame = tk.Frame(parent, bg=COLOR_PANEL)
        switch_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        switch_label = tk.Label(
            switch_frame,
            text="Режим работы:",
            font=("Arial", 10, "bold"),
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        switch_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.mode_switch_var = tk.BooleanVar(value=False)
        self.mode_switch = tk.Checkbutton(
            switch_frame,
            text="Локальное кодирование файла",
            variable=self.mode_switch_var,
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_PANEL,
            activeforeground=COLOR_TEXT_PRIMARY,
            selectcolor=COLOR_PANEL,
            command=self._on_mode_switch_changed
        )
        self.mode_switch.pack(side=tk.LEFT)
    
    def _create_local_file_panel(self, parent):
        """Панель для локального кодирования файлов"""
        self.local_file_frame = tk.LabelFrame(
            parent,
            text=f"{EMOJI_FILE} Локальное кодирование файла",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=PADDING_FRAME,
            pady=PADDING_FRAME
        )
        self.local_file_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Выбор входного файла
        input_frame = tk.Frame(self.local_file_frame, bg=COLOR_PANEL)
        input_frame.pack(fill=tk.X, pady=5)
        
        input_label = tk.Label(
            input_frame,
            text="Входной файл:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=15,
            anchor=tk.W
        )
        input_label.pack(side=tk.LEFT)
        
        self.local_input_entry = tk.Entry(
            input_frame,
            textvariable=self.file_path_var,
            font=FONT_NORMAL
        )
        self.local_input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.local_input_browse_btn = tk.Button(
            input_frame,
            text="Обзор...",
            font=FONT_NORMAL,
            command=self._browse_input_file,
            cursor='hand2'
        )
        self.local_input_browse_btn.pack(side=tk.LEFT)
        
        # Выбор выходного контейнера
        output_frame = tk.Frame(self.local_file_frame, bg=COLOR_PANEL)
        output_frame.pack(fill=tk.X, pady=5)
        
        output_label = tk.Label(
            output_frame,
            text="Выходной контейнер:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=15,
            anchor=tk.W
        )
        output_label.pack(side=tk.LEFT)
        
        self.local_output_entry = tk.Entry(
            output_frame,
            textvariable=self.local_output_path_var,
            font=FONT_NORMAL
        )
        self.local_output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.local_output_browse_btn = tk.Button(
            output_frame,
            text="Обзор...",
            font=FONT_NORMAL,
            command=self._browse_output_container,
            cursor='hand2'
        )
        self.local_output_browse_btn.pack(side=tk.LEFT)
        
        # Скрываем панель по умолчанию (будет показана при переключении режима)
        self.local_file_frame.pack_forget()
    
    def _create_local_start_button(self, parent):
        """Создает кнопку запуска для локального режима"""
        self.local_start_button_frame = tk.Frame(parent, bg=COLOR_BACKGROUND)
        self.local_start_button_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        self.local_start_button = tk.Button(
            self.local_start_button_frame,
            text=f"{EMOJI_PLAY} ЗАПУСТИТЬ КОДИРОВАНИЕ",
            font=FONT_BUTTON,
            bg=COLOR_SUCCESS,
            fg='white',
            command=self._start_encryption,
            cursor='hand2'
        )
        self.local_start_button.pack(fill=tk.X, pady=5)
        
        # Скрываем по умолчанию
        self.local_start_button_frame.pack_forget()
    
    def _browse_input_file(self):
        """Выбор входного файла для локального кодирования"""
        filename = filedialog.askopenfilename(
            title="Выберите файл для кодирования",
            filetypes=[("Все файлы", "*.*")]
        )
        if filename:
            self.file_path_var.set(filename)
            
            # Автоматически генерируем имя контейнера на основе входного файла
            base_name = os.path.splitext(filename)[0]  # Имя файла без расширения
            container_path = base_name + ".bin"
            self.local_output_path_var.set(container_path)
    
    def _browse_output_container(self):
        """Выбор пути сохранения контейнера"""
        filename = filedialog.asksaveasfilename(
            title="Сохранить контейнер как",
            defaultextension=".bin",
            filetypes=[("LightCrypto Container", "*.bin"), ("Все файлы", "*.*")]
        )
        if filename:
            self.local_output_path_var.set(filename)
    
    def _on_mode_switch_changed(self):
        """Обработка переключения между сетевым и локальным режимом"""
        is_local_mode = self.mode_switch_var.get()
        
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Canvas):
                canvas = widget
                scrollable_frame = canvas.winfo_children()[0]
                
                # Находим терминальную панель для правильного размещения элементов
                terminal_frame = None
                for child in scrollable_frame.winfo_children():
                    if isinstance(child, tk.LabelFrame):
                        text = child.cget("text")
                        if "Терминал" in text or "📋" in text:
                            terminal_frame = child
                            break
                
                if is_local_mode:
                    # Локальный режим - скрываем все сетевые панели
                    for child in scrollable_frame.winfo_children():
                        if isinstance(child, tk.LabelFrame):
                            text = child.cget("text")
                            if "TAP" in text or "tap" in text.lower() or "Сетевые параметры" in text or "🌐" in text:
                                child.pack_forget()
                    
                    # Показываем панель локального кодирования ПЕРЕД терминалом
                    if terminal_frame:
                        self.local_file_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION, before=terminal_frame)
                    else:
                        self.local_file_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
                    
                    # Показываем кнопку запуска ПЕРЕД терминалом (после панели файла)
                    if hasattr(self, 'local_start_button_frame'):
                        if terminal_frame:
                            self.local_start_button_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION, before=terminal_frame)
                        else:
                            self.local_start_button_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
                else:
                    # Сетевой режим - показываем сетевые панели ПЕРЕД терминалом
                    # Сначала находим все сетевые панели и упаковываем их в правильном порядке
                    tap_frame = None
                    network_frame = None
                    for child in scrollable_frame.winfo_children():
                        if isinstance(child, tk.LabelFrame):
                            text = child.cget("text")
                            if "TAP" in text or "tap" in text.lower():
                                tap_frame = child
                            elif "Сетевые параметры" in text or "🌐" in text:
                                network_frame = child
                    
                    # Упаковываем сетевые панели ПЕРЕД терминалом в правильном порядке
                    if terminal_frame:
                        if tap_frame:
                            tap_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION, before=terminal_frame)
                        if network_frame:
                            network_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION, before=terminal_frame)
                    else:
                        # Если терминал не найден, упаковываем в обычном порядке
                        if tap_frame:
                            tap_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
                        if network_frame:
                            network_frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
                    
                    # Скрываем панель локального кодирования и кнопку запуска
                    self.local_file_frame.pack_forget()
                    if hasattr(self, 'local_start_button_frame'):
                        self.local_start_button_frame.pack_forget()
                    
                    # Вызываем родительский метод для обработки сетевых режимов
                    super()._on_mode_changed()
    
    def _on_mode_changed(self):
        """Обработка изменения режима работы (только для сетевых режимов)"""
        # Этот метод вызывается только когда переключатель в сетевом режиме
        if hasattr(self, 'mode_switch_var') and self.mode_switch_var.get():
            return  # Игнорируем, если включен локальный режим
        
        super()._on_mode_changed()
    
    def _create_terminal_panel(self, parent):
        """Встроенный терминал с правильным callback"""
        frame = tk.LabelFrame(
            parent,
            text="📋 Терминал",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=5,
            pady=5
        )
        frame.pack(fill=tk.BOTH, expand=True, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        self.terminal = EmbeddedTerminal(frame, self)
        # Устанавливаем callback на наш метод on_process_finished
        self.terminal.on_process_finished = self.on_process_finished
    
    def on_process_finished(self):
        """Обработка завершения процесса - возврат кнопки в исходное состояние"""
        # Проверяем, какой режим активен
        if hasattr(self, 'mode_switch_var') and self.mode_switch_var.get():
            # Локальный режим - возвращаем локальную кнопку
            if hasattr(self, 'local_start_button'):
                self.local_start_button.config(
                    text=f"{EMOJI_PLAY} ЗАПУСТИТЬ КОДИРОВАНИЕ",
                    bg=COLOR_SUCCESS
                )
        else:
            # Сетевой режим - возвращаем сетевую кнопку
            if hasattr(self, 'start_button'):
                self.start_button.config(
                    text=f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ",
                    bg=COLOR_SUCCESS
                )
    
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
        
        # Проверяем переключатель режимов
        if hasattr(self, 'mode_switch_var') and self.mode_switch_var.get():
            # Локальный режим
            mode = 'local_file'
            input_path = self.file_path_var.get().strip()
            output_path = self.local_output_path_var.get().strip()
            
            if not input_path:
                messagebox.showerror("Ошибка", "Выберите входной файл!")
                return
            
            if not os.path.isfile(input_path):
                messagebox.showerror("Ошибка", f"Файл не найден: {input_path}")
                return
            
            if not output_path:
                messagebox.showerror("Ошибка", "Укажите путь для сохранения контейнера!")
                return
            
            # Получение параметров кодека
            params = self.codec_panel.get_params()
            
            if not params['csv_path']:
                messagebox.showerror("Ошибка", "CSV файл не выбран!")
                return
            
            # Сохранение параметров
            self.codec_panel.save_to_config()
            self.config.save()
            
            # Формирование команды для локального кодирования
            cmd = [
                FILE_ENCODE,
                input_path,
                output_path,
                '--codec', params['csv_path'],
                '--M', str(params['M']),
                '--Q', str(params['Q']),
                '--fun', str(params['funType']),
                '--h1', str(params['h1']),
                '--h2', str(params['h2'])
            ]
            
            # Вывод команды
            from common.utils import format_command_list
            self.terminal.print_to_terminal(
                f"{EMOJI_INFO} Команда: {format_command_list(cmd)}",
                'info'
            )
            
            # Запуск
            self.terminal.run_process(cmd, use_xterm=False)
            
            # Обновление кнопки (локальный режим)
            if hasattr(self, 'local_start_button'):
                self.local_start_button.config(
                    text=f"{EMOJI_STOP} ОСТАНОВИТЬ КОДИРОВАНИЕ",
                    bg=COLOR_ERROR
                )
            return
        
        # Обработка сетевых режимов (tap, msg, file)
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
        
        # Валидация для режима файлов
        if mode == 'file':
            file_path = self.file_path_var.get().strip()
            if not file_path:
                messagebox.showerror("Ошибка", "Выберите файл для отправки!")
                return
            
            if not os.path.isfile(file_path):
                messagebox.showerror("Ошибка", f"Файл не найден: {file_path}")
                return
        
        # Получение параметров кодека
        params = self.codec_panel.get_params()
        
        if not params['csv_path']:
            messagebox.showerror("Ошибка", "CSV файл не выбран!")
            return
        
        # Сохранение параметров
        self.config.set_custom_encrypt_ip(ip)
        self.config.set_custom_port(port)
        self.config.set_custom_msg_mode(mode == 'msg')
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
        
        # Добавляем параметры отладки и внесения ошибок
        if params.get('debug', False):
            cmd.append('--debug')
        if params.get('injectErrors', False):
            cmd.append('--inject-errors')
            cmd.append('--error-rate')
            cmd.append(str(params.get('errorRate', 0.01)))
        
        if mode == 'msg':
            cmd.append('--msg')
        elif mode == 'file':
            cmd.append('--file')
            cmd.append(self.file_path_var.get())
        
        cmd.append(ip)
        cmd.append(str(port))
        
        # Вывод команды
        from common.utils import format_command_list
        self.terminal.print_to_terminal(
            f"{EMOJI_INFO} Команда: {format_command_list(cmd)}",
            'info'
        )
        
        # Запуск
        # Используем стандартный метод terminal.run_process для всех режимов
        self.terminal.run_process(cmd, use_xterm=False)
        
        # Показать поле ввода если режим сообщений
        if mode == 'msg':
            self.terminal.show_input_field(True)
        
        # Обновление кнопки (сетевой режим)
        if hasattr(self, 'start_button'):
            self.start_button.config(
                text=f"{EMOJI_STOP} ОСТАНОВИТЬ ШИФРОВАНИЕ",
                bg=COLOR_ERROR
            )


# Импорт для валидации
from common.utils import validate_ip, validate_port
from tkinter import ttk

