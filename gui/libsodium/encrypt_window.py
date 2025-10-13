"""
LightCrypto GUI - LibSodium Encrypt (Отправитель)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import re

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


class LibSodiumEncryptGUI:
    """
    GUI для LibSodium шифрования (Отправитель)
    """
    
    def __init__(self, config: ConfigManager, on_back):
        self.config = config
        self.on_back_callback = on_back
        self.terminal = None
        
        self.root = tk.Tk()
        self.root.title("🔐 LightCrypto - LibSodium Encrypt (Отправитель)")
        self.root.geometry(f"{WINDOW_DEFAULT_WIDTH}x{WINDOW_DEFAULT_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=COLOR_BACKGROUND)
        
        # Переменные
        self.ip_var = tk.StringVar(value=config.get_libsodium_encrypt_ip())
        self.port_var = tk.StringVar(value=str(config.get_libsodium_port()))
        self.msg_mode_var = tk.BooleanVar(value=config.get_libsodium_msg_mode())
        self.tap_status_var = tk.StringVar(value=STATUS_TAP_NOT_CREATED)
        
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
        
        # Поддержка прокрутки колесиком мыши
        self._bind_mouse_wheel(main_canvas, scrollable_frame)
        
        # Панели
        self._create_tap_panel(scrollable_frame)
        self._create_network_panel(scrollable_frame)
        self._create_control_panel(scrollable_frame)
        self._create_terminal_panel(scrollable_frame)
        self._create_utils_panel(scrollable_frame)
        
        # Размещение
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
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
            text=f"{EMOJI_SETTINGS} Создать TAP-A",
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
        
        # IP-адрес
        ip_frame = tk.Frame(frame, bg=COLOR_PANEL)
        ip_frame.pack(fill=tk.X, pady=5)
        
        ip_label = tk.Label(
            ip_frame,
            text="IP-адрес получателя:",
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
        self._create_tooltip(ip_entry, TOOLTIP_IP_ENCRYPT)
        
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
        
        # Режим сообщений
        msg_check = tk.Checkbutton(
            frame,
            text="☐ Режим сообщений (--msg)",
            variable=self.msg_mode_var,
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_PANEL,
            selectcolor=COLOR_PANEL,
            command=self._on_msg_mode_changed
        )
        msg_check.pack(anchor=tk.W, pady=5)
        
        self._create_tooltip(msg_check, TOOLTIP_MSG_MODE)
    
    def _create_control_panel(self, parent):
        """Главная кнопка запуска/остановки"""
        frame = tk.Frame(parent, bg=COLOR_BACKGROUND)
        frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        self.start_button = tk.Button(
            frame,
            text=f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ",
            font=('Arial', 14, 'bold'),
            bg=COLOR_SUCCESS,
            fg='white',
            command=self._toggle_encryption,
            cursor='hand2',
            height=2
        )
        self.start_button.pack(fill=tk.X, pady=10)
    
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
    
    def _create_utils_panel(self, parent):
        """Панель тестовых утилит"""
        frame = tk.LabelFrame(
            parent,
            text="🧪 Генерация тестового трафика",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=PADDING_FRAME,
            pady=PADDING_FRAME
        )
        frame.pack(fill=tk.X, padx=PADDING_SECTION, pady=PADDING_SECTION)
        
        # Первый ряд кнопок
        row1 = tk.Frame(frame, bg=COLOR_PANEL)
        row1.pack(fill=tk.X, pady=5)
        
        self.ping_btn = tk.Button(
            row1,
            text=f"{EMOJI_PING} ping 10.0.0.2",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=lambda: self._run_test_util("ping 10.0.0.2"),
            cursor='hand2'
        )
        self.ping_btn.pack(side=tk.LEFT, padx=5)
        
        self.iperf_tcp_btn = tk.Button(
            row1,
            text=f"{EMOJI_IPERF} iperf TCP",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=lambda: self._run_test_util("iperf -c 10.0.0.2 -t 10"),
            cursor='hand2'
        )
        self.iperf_tcp_btn.pack(side=tk.LEFT, padx=5)
        
        self.iperf_udp_btn = tk.Button(
            row1,
            text=f"{EMOJI_IPERF} iperf UDP",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=lambda: self._run_test_util("iperf -c 10.0.0.2 -u -t 10 -b 100M"),
            cursor='hand2'
        )
        self.iperf_udp_btn.pack(side=tk.LEFT, padx=5)
        
        # Второй ряд кнопок
        row2 = tk.Frame(frame, bg=COLOR_PANEL)
        row2.pack(fill=tk.X, pady=5)
        
        self.hping_syn_btn = tk.Button(
            row2,
            text=f"{EMOJI_HPING} hping3 SYN",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=lambda: self._run_test_util("hping3 10.0.0.2 -S -p 80 -c 10"),
            cursor='hand2'
        )
        self.hping_syn_btn.pack(side=tk.LEFT, padx=5)
        
        self.hping_udp_btn = tk.Button(
            row2,
            text=f"{EMOJI_HPING} hping3 UDP",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=lambda: self._run_test_util("hping3 10.0.0.2 -2 -p 5000 -c 10"),
            cursor='hand2'
        )
        self.hping_udp_btn.pack(side=tk.LEFT, padx=5)
        
        # Сохраняем ссылки на кнопки для блокировки в режиме сообщений
        self.test_buttons = [
            self.ping_btn, self.iperf_tcp_btn, self.iperf_udp_btn,
            self.hping_syn_btn, self.hping_udp_btn
        ]
    
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
        exists, ip = get_tap_status(TAP_NAMES['encrypt'])
        
        if exists and ip:
            self.tap_status_var.set(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['encrypt']} ({ip})")
        elif exists:
            self.tap_status_var.set(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['encrypt']}")
        else:
            self.tap_status_var.set(f"Статус: {STATUS_TAP_NOT_CREATED}")
        
        # Повторная проверка через 2 секунды
        self.root.after(2000, self._update_tap_status)
    
    def _create_tap(self):
        """Создание TAP-интерфейса"""
        self.terminal.print_to_terminal(f"{EMOJI_SETTINGS} Создание {TAP_NAMES['encrypt']}...", 'info')
        
        try:
            result = subprocess.run(
                ['sudo', 'bash', SETUP_TAP_A],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.terminal.print_to_terminal(f"{EMOJI_SUCCESS} {TAP_NAMES['encrypt']} создан успешно!", 'success')
                self.terminal.print_to_terminal(result.stdout, 'info')
            else:
                self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибка создания {TAP_NAMES['encrypt']}", 'error')
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
        
        self.terminal.print_to_terminal(f"{EMOJI_CLEAN} Удаление {TAP_NAMES['encrypt']}...", 'warning')
        
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'delete', TAP_NAMES['encrypt']],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self.terminal.print_to_terminal(f"{EMOJI_SUCCESS} {TAP_NAMES['encrypt']} удален", 'success')
            else:
                self.terminal.print_to_terminal(f"{EMOJI_WARNING} {TAP_NAMES['encrypt']} не найден или уже удален", 'warning')
        
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
        
        # Сохранение параметров
        self.config.set_libsodium_encrypt_ip(ip)
        self.config.set_libsodium_port(port)
        self.config.set_libsodium_msg_mode(self.msg_mode_var.get())
        self.config.save()
        
        # Формирование команды
        cmd = ['sudo', TAP_ENCRYPT]
        
        if self.msg_mode_var.get():
            cmd.append('--msg')
        
        cmd.append(ip)
        cmd.append(str(port))
        
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
    
    def _stop_encryption(self):
        """Остановка шифрования"""
        self.terminal.stop_process()
        
        # Скрыть поле ввода
        self.terminal.show_input_field(False)
        
        # Обновление кнопки
        self.start_button.config(
            text=f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ",
            bg=COLOR_SUCCESS
        )
    
    def _on_msg_mode_changed(self):
        """Обработка изменения режима сообщений"""
        is_msg_mode = self.msg_mode_var.get()
        
        # Блокировка кнопок тестовых утилит
        state = tk.DISABLED if is_msg_mode else tk.NORMAL
        
        for btn in self.test_buttons:
            btn.config(state=state)
        
        if is_msg_mode:
            self.terminal.print_to_terminal(
                f"{EMOJI_INFO} Режим сообщений включен. Тестовые утилиты отключены.",
                'info'
            )
    
    def _run_test_util(self, command: str):
        """Запуск тестовой утилиты в отдельном терминале"""
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
            self.terminal.print_to_terminal(f"{EMOJI_INFO} Запущена утилита: {command}", 'info')
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

