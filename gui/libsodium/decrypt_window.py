"""
LightCrypto GUI - LibSodium Decrypt (Получатель)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.constants import *
from common.config import ConfigManager
from common.terminal import EmbeddedTerminal
from common.utils import (
    validate_ip, validate_port, check_tap_interface,
    get_tap_status, find_terminal_emulator
)


class LibSodiumDecryptGUI:
    """
    GUI для LibSodium шифрования (Получатель)
    """
    
    def __init__(self, config: ConfigManager, on_back):
        self.config = config
        self.on_back_callback = on_back
        self.terminal = None
        
        self.root = tk.Tk()
        self.root.title("🔐 LightCrypto - LibSodium Decrypt (Получатель)")
        self.root.geometry(f"{WINDOW_DEFAULT_WIDTH}x{WINDOW_DEFAULT_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=COLOR_BACKGROUND)
        
        # Переменные
        self.ip_var = tk.StringVar(value=DEFAULT_DECRYPT_IP)
        self.port_var = tk.StringVar(value=str(config.get_libsodium_port()))
        self.msg_mode_var = tk.BooleanVar(value=config.get_libsodium_msg_mode())
        self.tap_status_var = tk.StringVar(value=STATUS_TAP_NOT_CREATED)
        
        # IP адрес TAP-B интерфейса
        self.tap_b_ip_var = tk.StringVar(value="10.0.0.2/24")
        
        # Режим работы: 'tap', 'msg', 'file'
        self.mode_var = tk.StringVar(value='tap')
        self.output_path_var = tk.StringVar(value='')
        
        self._create_widgets()
        self._update_tap_status()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
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
        
        # Панели
        self._create_tap_panel(scrollable_frame)
        self._create_network_panel(scrollable_frame)
        self._create_terminal_panel(scrollable_frame)
        self._create_utils_panel(scrollable_frame)
        
        # Размещение
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Поддержка прокрутки колесиком мыши (ПОСЛЕ создания всех виджетов)
        self._bind_mouse_wheel(main_canvas, scrollable_frame)
    
    def _create_tap_panel(self, parent):
        """Панель управления TAP-интерфейсом"""
        frame = tk.LabelFrame(
            parent,
            text=f"{EMOJI_SETTINGS} Управление TAP-интерфейсом",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=PADDING_FRAME,
            pady=PADDING_FRAME
        )
        frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Кнопки
        btn_frame = tk.Frame(frame, bg=COLOR_PANEL)
        btn_frame.pack(fill=tk.X, pady=5)
        
        create_btn = tk.Button(
            btn_frame,
            text=f"{EMOJI_SETTINGS} Создать TAP-B",
            font=FONT_BUTTON,
            bg=COLOR_SUCCESS,
            fg='white',
            command=self._create_tap,
            cursor='hand2'
        )
        create_btn.pack(side=tk.LEFT, padx=5)
        
        clean_btn = tk.Button(
            btn_frame,
            text=f"{EMOJI_CLEAN} Очистить TAP",
            font=FONT_BUTTON,
            bg=COLOR_WARNING,
            fg='white',
            command=self._clean_tap,
            cursor='hand2'
        )
        clean_btn.pack(side=tk.LEFT, padx=5)
        
        # IP адрес TAP-B
        ip_frame = tk.Frame(frame, bg=COLOR_PANEL)
        ip_frame.pack(fill=tk.X, pady=5)
        
        ip_label = tk.Label(
            ip_frame,
            text="TAP-B IP:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=15,
            anchor=tk.W
        )
        ip_label.pack(side=tk.LEFT)
        
        ip_entry = tk.Entry(
            ip_frame,
            textvariable=self.tap_b_ip_var,
            font=FONT_NORMAL,
            width=15
        )
        ip_entry.pack(side=tk.LEFT, padx=5)
        
        # Статус
        status_label = tk.Label(
            frame,
            textvariable=self.tap_status_var,
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        status_label.pack(anchor=tk.W, pady=5)
    
    def _create_network_panel(self, parent):
        """Панель сетевых параметров"""
        frame = tk.LabelFrame(
            parent,
            text="🌐 Сетевые параметры",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=PADDING_FRAME,
            pady=PADDING_FRAME
        )
        frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Выбор режима работы
        mode_frame = tk.LabelFrame(
            frame,
            text="Режим работы",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=5,
            pady=5
        )
        mode_frame.pack(fill=tk.X, pady=5)
        
        tap_radio = tk.Radiobutton(
            mode_frame,
            text="🔀 Ethernet кадры (TAP)",
            variable=self.mode_var,
            value='tap',
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_PANEL,
            selectcolor=COLOR_PANEL,
            command=self._on_mode_changed
        )
        tap_radio.pack(anchor=tk.W)
        
        msg_radio = tk.Radiobutton(
            mode_frame,
            text="💬 Текстовые сообщения (--msg)",
            variable=self.mode_var,
            value='msg',
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_PANEL,
            selectcolor=COLOR_PANEL,
            command=self._on_mode_changed
        )
        msg_radio.pack(anchor=tk.W)
        self._create_tooltip(msg_radio, TOOLTIP_MSG_MODE)
        
        file_radio = tk.Radiobutton(
            mode_frame,
            text=f"{EMOJI_FILE} Прием файлов (--file)",
            variable=self.mode_var,
            value='file',
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_PANEL,
            selectcolor=COLOR_PANEL,
            command=self._on_mode_changed
        )
        file_radio.pack(anchor=tk.W)
        self._create_tooltip(file_radio, TOOLTIP_FILE_MODE)
        
        # Панель выбора пути сохранения (показывается только в режиме file)
        self.file_output_frame = tk.Frame(frame, bg=COLOR_PANEL)
        
        output_label = tk.Label(
            self.file_output_frame,
            text="Путь для сохранения (необязательно):",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            anchor=tk.W
        )
        output_label.pack(fill=tk.X, pady=(5, 0))
        
        output_entry_frame = tk.Frame(self.file_output_frame, bg=COLOR_PANEL)
        output_entry_frame.pack(fill=tk.X, pady=2)
        
        self.output_entry = tk.Entry(
            output_entry_frame,
            textvariable=self.output_path_var,
            font=FONT_NORMAL
        )
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.output_browse_btn = tk.Button(
            output_entry_frame,
            text=f"{EMOJI_FOLDER} Выбрать",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=self._browse_output,
            cursor='hand2'
        )
        self.output_browse_btn.pack(side=tk.RIGHT)
        self._create_tooltip(self.output_entry, TOOLTIP_FILE_OUTPUT)
        
        output_hint = tk.Label(
            self.file_output_frame,
            text="(Пусто = сохранить с оригинальным именем в текущей папке)",
            font=('Arial', 8),
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_SECONDARY
        )
        output_hint.pack(anchor=tk.W)
        
        # Разделитель
        separator1 = ttk.Separator(frame, orient='horizontal')
        separator1.pack(fill=tk.X, pady=8)
        
        # IP-адрес
        ip_frame = tk.Frame(frame, bg=COLOR_PANEL)
        ip_frame.pack(fill=tk.X, pady=5)
        
        ip_label = tk.Label(
            ip_frame,
            text="IP прослушивания:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=20,
            anchor=tk.W
        )
        ip_label.pack(side=tk.LEFT)
        
        ip_entry = tk.Entry(
            ip_frame,
            textvariable=self.ip_var,
            font=FONT_NORMAL,
            width=20
        )
        ip_entry.pack(side=tk.LEFT, padx=5)
        
        # Tooltip для IP
        self._create_tooltip(ip_entry, TOOLTIP_IP_DECRYPT)
        
        # Порт
        port_frame = tk.Frame(frame, bg=COLOR_PANEL)
        port_frame.pack(fill=tk.X, pady=5)
        
        port_label = tk.Label(
            port_frame,
            text="Порт:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=20,
            anchor=tk.W
        )
        port_label.pack(side=tk.LEFT)
        
        port_entry = tk.Entry(
            port_frame,
            textvariable=self.port_var,
            font=FONT_NORMAL,
            width=10
        )
        port_entry.pack(side=tk.LEFT, padx=5)
        
        self._create_tooltip(port_entry, TOOLTIP_PORT)
        
        # Разделитель
        separator2 = ttk.Separator(frame, orient='horizontal')
        separator2.pack(fill=tk.X, pady=8)
        
        # Кнопка запуска/остановки (компактная)
        self.start_button = tk.Button(
            frame,
            text=f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ",
            font=FONT_BUTTON,
            bg=COLOR_SUCCESS,
            fg='white',
            command=self._toggle_encryption,
            cursor='hand2'
        )
        self.start_button.pack(fill=tk.X, pady=5)
        
        # Инициализация видимости элементов
        self._on_mode_changed()
    
    def _create_terminal_panel(self, parent):
        """Встроенный терминал"""
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
        # Устанавливаем callback для обновления кнопки при завершении процесса
        self.terminal.on_process_finished = self._on_process_finished
    
    def _create_utils_panel(self, parent):
        """Панель сервисов для тестирования"""
        frame = tk.LabelFrame(
            parent,
            text="🛰️ Сервисы для тестирования",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=PADDING_FRAME,
            pady=PADDING_FRAME
        )
        frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Кнопки сервисов
        row1 = tk.Frame(frame, bg=COLOR_PANEL)
        row1.pack(fill=tk.X, pady=5)
        
        iperf_tcp_srv_btn = tk.Button(
            row1,
            text=f"{EMOJI_SERVER} iperf TCP сервер",
            font=FONT_BUTTON,
            bg=COLOR_DECRYPT,
            fg='white',
            command=lambda: self._run_service(f"iperf -s -B {self._get_tap_b_ip()}"),
            cursor='hand2'
        )
        iperf_tcp_srv_btn.pack(side=tk.LEFT, padx=5)
        
        iperf_udp_srv_btn = tk.Button(
            row1,
            text=f"{EMOJI_SERVER} iperf UDP сервер",
            font=FONT_BUTTON,
            bg=COLOR_DECRYPT,
            fg='white',
            command=lambda: self._run_service(f"iperf -s -u -B {self._get_tap_b_ip()}"),
            cursor='hand2'
        )
        iperf_udp_srv_btn.pack(side=tk.LEFT, padx=5)
        
        tcpdump_btn = tk.Button(
            row1,
            text=f"{EMOJI_TCPDUMP} tcpdump tap1",
            font=FONT_BUTTON,
            bg=COLOR_DECRYPT,
            fg='white',
            command=lambda: self._run_service("sudo tcpdump -i tap1 -v"),
            cursor='hand2'
        )
        tcpdump_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_tooltip(self, widget, text):
        """Создание всплывающей подсказки"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(
                tooltip,
                text=text,
                background=COLOR_STATUS_WARN,
                relief=tk.SOLID,
                borderwidth=1,
                font=FONT_NORMAL,
                wraplength=400,
                justify=tk.LEFT,
                padx=10,
                pady=5
            )
            label.pack()
            
            widget.tooltip = tooltip
        
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)
    
    def _update_tap_status(self):
        """Обновление статуса TAP интерфейса"""
        exists, ip = get_tap_status(TAP_NAMES['decrypt'])
        
        if exists and ip:
            self.tap_status_var.set(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['decrypt']} ({ip})")
        elif exists:
            self.tap_status_var.set(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['decrypt']}")
        else:
            self.tap_status_var.set(f"Статус: {STATUS_TAP_NOT_CREATED}")
        
        # Повторная проверка через 2 секунды
        self.root.after(2000, self._update_tap_status)
    
    def _create_tap(self):
        """Создание TAP-интерфейса"""
        self.terminal.print_to_terminal(f"{EMOJI_SETTINGS} Создание {TAP_NAMES['decrypt']}...", 'info')
        
        try:
            tap_b_ip = self.tap_b_ip_var.get().strip()
            result = subprocess.run(
                ['sudo', 'bash', SETUP_TAP_B, tap_b_ip],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.terminal.print_to_terminal(f"{EMOJI_SUCCESS} {TAP_NAMES['decrypt']} создан успешно!", 'success')
                self.terminal.print_to_terminal(result.stdout, 'info')
            else:
                self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибка создания {TAP_NAMES['decrypt']}", 'error')
                self.terminal.print_to_terminal(result.stderr, 'error')
        
        except subprocess.TimeoutExpired:
            self.terminal.print_to_terminal(f"{EMOJI_ERROR} Timeout при создании TAP", 'error')
        except Exception as e:
            self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибка: {e}", 'error')
    
    def _clean_tap(self):
        """Очистка TAP-интерфейса"""
        if self.terminal and self.terminal.is_running:
            messagebox.showwarning(
                "Внимание",
                "Сначала остановите процесс шифрования!"
            )
            return
        
        self.terminal.print_to_terminal(f"{EMOJI_CLEAN} Удаление {TAP_NAMES['decrypt']}...", 'warning')
        
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'delete', TAP_NAMES['decrypt']],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self.terminal.print_to_terminal(f"{EMOJI_SUCCESS} {TAP_NAMES['decrypt']} удален", 'success')
            else:
                self.terminal.print_to_terminal(f"{EMOJI_WARNING} {TAP_NAMES['decrypt']} не найден или уже удален", 'warning')
        
        except Exception as e:
            self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибка: {e}", 'error')
    
    def _toggle_encryption(self):
        """Запуск/остановка шифрования"""
        if self.terminal.is_running:
            self._stop_encryption()
        else:
            self._start_encryption()
    
    def _start_encryption(self):
        """Запуск шифрования"""
        # Валидация
        port_str = self.port_var.get().strip()
        mode = self.mode_var.get()
        
        try:
            port = int(port_str)
            if not validate_port(port):
                raise ValueError()
        except:
            messagebox.showerror("Ошибка", f"Некорректный порт! Допустимый диапазон: {PORT_MIN}-{PORT_MAX}")
            return
        
        # Сохранение параметров
        self.config.set_libsodium_port(port)
        self.config.set_libsodium_msg_mode(mode == 'msg')
        self.config.save()
        
        # Формирование команды
        cmd = ['sudo', TAP_DECRYPT]
        
        if mode == 'msg':
            cmd.append('--msg')
        elif mode == 'file':
            cmd.append('--file')
            # Добавляем путь для сохранения если указан
            output_path = self.output_path_var.get().strip()
            if output_path:
                cmd.append('--output')
                cmd.append(output_path)
        
        cmd.append(str(port))
        
        # Запуск
        self.terminal.run_process(cmd, use_xterm=False)
        
        # Обновление кнопки
        self.start_button.config(
            text=f"{EMOJI_STOP} ОСТАНОВИТЬ ШИФРОВАНИЕ",
            bg=COLOR_ERROR
        )
    
    def _stop_encryption(self):
        """Остановка шифрования"""
        self.terminal.stop_process()
        
        # Обновление кнопки
        self._reset_start_button()
    
    def _on_process_finished(self):
        """Callback при завершении процесса (автоматическом или ручном)"""
        # Обновление кнопки
        self._reset_start_button()
    
    def _reset_start_button(self):
        """Сброс кнопки запуска в исходное состояние"""
        self.start_button.config(
            text=f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ",
            bg=COLOR_SUCCESS
        )
    
    def _on_mode_changed(self):
        """Обработка изменения режима работы"""
        mode = self.mode_var.get()
        
        # Показать/скрыть панель выбора пути сохранения
        if mode == 'file':
            self.file_output_frame.pack(fill=tk.X, pady=5, before=self.file_output_frame.master.children['!separator'])
        else:
            self.file_output_frame.pack_forget()
        
        # Блокировка кнопок тестовых утилит (только в режиме TAP)
        # Проверяем, что test_buttons уже созданы
        if hasattr(self, 'test_buttons'):
            state = tk.NORMAL if mode == 'tap' else tk.DISABLED
            
            for btn in self.test_buttons:
                btn.config(state=state)
        
        # Информационные сообщения (только если терминал уже создан)
        if hasattr(self, 'terminal') and self.terminal:
            if mode == 'msg':
                self.terminal.print_to_terminal(
                    f"{EMOJI_INFO} Режим сообщений включен. Ожидание сообщений...",
                    'info'
                )
            elif mode == 'file':
                self.terminal.print_to_terminal(
                    f"{EMOJI_INFO} Режим приема файлов включен. Ожидание файла...",
                    'info'
                )
            elif mode == 'tap':
                self.terminal.print_to_terminal(
                    f"{EMOJI_INFO} Режим Ethernet-кадров активен.",
                    'info'
                )
    
    def _browse_output(self):
        """Выбор пути для сохранения файла"""
        from tkinter import filedialog
        
        initial_dir = self.config.get_last_output_dir()
        
        filepath = filedialog.asksaveasfilename(
            title="Выберите путь для сохранения файла",
            initialdir=initial_dir,
            defaultextension=".*",
            filetypes=[
                ("Все файлы", "*.*"),
                ("Изображения", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Документы", "*.pdf *.doc *.docx *.txt"),
                ("Архивы", "*.zip *.rar *.7z *.tar *.gz"),
            ]
        )
        
        if filepath:
            self.output_path_var.set(filepath)
            # Сохранить директорию
            import os
            self.config.set_last_output_dir(os.path.dirname(filepath))
            self.config.save()
            
            self.terminal.print_to_terminal(
                f"{EMOJI_FILE} Путь сохранения: {os.path.basename(filepath)}",
                'success'
            )
    
    def _get_tap_b_ip(self):
        """Получить IP адрес TAP-B (без маски)"""
        tap_b_ip = self.tap_b_ip_var.get().strip()
        # Убираем маску если есть
        if '/' in tap_b_ip:
            return tap_b_ip.split('/')[0]
        return tap_b_ip
    
    def _run_service(self, command: str):
        """Запуск сервиса в отдельном терминале"""
        terminal = find_terminal_emulator()
        
        if not terminal:
            messagebox.showerror(
                "Ошибка",
                "Не найден эмулятор терминала!\n"
                "Установите gnome-terminal, konsole или xterm."
            )
            return
        
        try:
            cmd = [terminal, '--', 'bash', '-c', f'{command}; read -p "Нажмите Enter для закрытия..."']
            subprocess.Popen(cmd)
            self.terminal.print_to_terminal(f"{EMOJI_INFO} Запущен сервис: {command}", 'info')
        except Exception as e:
            self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибка запуска: {e}", 'error')
    
    def _bind_mouse_wheel(self, canvas, frame):
        """
        Привязка прокрутки колесиком мыши к Canvas и всем дочерним виджетам
        
        Args:
            canvas: Canvas виджет
            frame: Frame внутри Canvas
        """
        def _on_mouse_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        
        def _on_mouse_wheel_linux_up(event):
            canvas.yview_scroll(-1, "units")
            return "break"
        
        def _on_mouse_wheel_linux_down(event):
            canvas.yview_scroll(1, "units")
            return "break"
        
        def bind_to_widget(widget):
            """Рекурсивно привязывает прокрутку ко всем виджетам"""
            # Для Windows и MacOS
            widget.bind('<MouseWheel>', _on_mouse_wheel, add='+')
            # Для Linux (X11)
            widget.bind('<Button-4>', _on_mouse_wheel_linux_up, add='+')
            widget.bind('<Button-5>', _on_mouse_wheel_linux_down, add='+')
            
            # Рекурсивно для всех дочерних виджетов
            for child in widget.winfo_children():
                bind_to_widget(child)
        
        # Привязываем к canvas и всем виджетам внутри frame
        bind_to_widget(canvas)
        bind_to_widget(frame)
    
    def _on_closing(self):
        """Обработка закрытия окна"""
        if self.terminal and self.terminal.is_running:
            response = messagebox.askyesno(
                "Подтверждение",
                "Процесс шифрования запущен. Остановить и закрыть?"
            )
            if response:
                self.terminal.stop_process()
            else:
                return
        
        self.config.save()
        self.root.destroy()
        if self.on_back_callback:
            self.on_back_callback()
    
    def run(self):
        """Запуск главного цикла окна"""
        self.root.mainloop()

