"""
LightCrypto GUI - Встроенный терминал
Двухпанельная структура: xterm + ScrolledText
Захват вывода процесса через PTY
"""

import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import os
import signal
import pty
import select
import fcntl
import struct
import termios
import re
import time
from typing import List, Optional

from .constants import *


class EmbeddedTerminal:
    """
    Встроенный терминал с двумя панелями:
    - Верхняя: xterm для интерактивного ввода (если доступен)
    - Нижняя: ScrolledText для вывода логов
    """
    
    def __init__(self, parent_widget, parent_gui):
        """
        Инициализация терминала
        
        Args:
            parent_widget: Родительский виджет Tkinter
            parent_gui: Ссылка на родительское GUI (для callback)
        """
        self.parent = parent_widget
        self.parent_gui = parent_gui
        self.process = None
        self.master_fd = None
        self.read_thread = None
        self.running = False
        self.on_process_finished = None  # Callback при завершении процесса
        
        # Создание контейнера
        self.container = tk.Frame(parent_widget, bg=COLOR_BACKGROUND)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Используем только однопанельный терминал (без xterm)
        self.xterm_available = False
        self._create_single_panel_terminal()
    
    def _check_xterm(self) -> bool:
        """Проверка доступности xterm"""
        try:
            result = subprocess.run(['which', 'xterm'],
                                  capture_output=True,
                                  timeout=2)
            return result.returncode == 0 and os.environ.get('DISPLAY')
        except Exception:
            return False
    
    def _create_two_panel_terminal(self):
        """Создание двухпанельного терминала (xterm + ScrolledText)"""
        # Верхняя панель - xterm
        xterm_frame = tk.Frame(self.container, height=TERMINAL_XTERM_HEIGHT,
                              bg=COLOR_BACKGROUND)
        xterm_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        xterm_frame.pack_propagate(False)
        
        self.xterm_frame = xterm_frame
        
        # Разделитель
        separator = tk.Frame(self.container, height=2, bg=COLOR_TEXT_SECONDARY)
        separator.pack(side=tk.TOP, fill=tk.X)
        
        # Нижняя панель - ScrolledText
        output_frame = tk.Frame(self.container, bg=COLOR_BACKGROUND)
        output_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        self._create_output_panel(output_frame)
    
    def _create_single_panel_terminal(self):
        """Создание однопанельного терминала (только ScrolledText)"""
        output_frame = tk.Frame(self.container, bg=COLOR_BACKGROUND)
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_output_panel(output_frame)
    
    def _create_output_panel(self, parent):
        """Создание панели вывода (ScrolledText)"""
        # Заголовок
        header_frame = tk.Frame(parent, bg=COLOR_PANEL)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        label = tk.Label(header_frame, text="📋 Вывод",
                        font=FONT_TITLE, bg=COLOR_PANEL,
                        fg=COLOR_TEXT_PRIMARY)
        label.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(header_frame, text=f"{EMOJI_CLEAN} Очистить",
                             font=FONT_BUTTON, bg=COLOR_PANEL,
                             command=self.clear_terminal)
        clear_btn.pack(side=tk.RIGHT, padx=5)
        
        # ScrolledText для вывода
        self.output_text = scrolledtext.ScrolledText(
            parent,
            font=FONT_TERMINAL,
            bg='#1E1E1E',  # Темный фон как в терминале
            fg='#FFFFFF',  # Белый текст
            insertbackground='#FFFFFF',
            wrap=tk.WORD,
            state=tk.DISABLED  # Read-only по умолчанию
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Конфигурация цветовых тегов для ANSI
        self.output_text.tag_config('error', foreground='#FF5555')
        self.output_text.tag_config('success', foreground='#50FA7B')
        self.output_text.tag_config('warning', foreground='#FFB86C')
        self.output_text.tag_config('info', foreground='#8BE9FD')
        
        # Поддержка прокрутки колесиком мыши
        self._bind_mouse_wheel(self.output_text)
        
        self.buffer_lines = 0  # Счетчик строк в буфере
        
        # Поле ввода для режима сообщений
        input_frame = tk.Frame(parent, bg=COLOR_PANEL)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        input_label = tk.Label(input_frame, text="💬", font=FONT_NORMAL,
                              bg=COLOR_PANEL, fg=COLOR_TEXT_PRIMARY)
        input_label.pack(side=tk.LEFT, padx=5)
        
        self.input_entry = tk.Entry(input_frame, font=FONT_NORMAL,
                                    bg='#2B2B2B', fg='#FFFFFF',
                                    insertbackground='#FFFFFF')
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.input_entry.bind('<Return>', lambda e: self.send_message())
        
        send_btn = tk.Button(input_frame, text=f"{EMOJI_SEND} Отправить",
                            font=FONT_BUTTON, bg=COLOR_SUCCESS, fg='white',
                            command=self.send_message, cursor='hand2')
        send_btn.pack(side=tk.RIGHT, padx=5)
        
        # Изначально скрываем поле ввода (показывается только в режиме сообщений)
        input_frame.pack_forget()
        self.input_frame = input_frame
    
    def print_to_terminal(self, message: str, tag: str = None):
        """
        Вывод сообщения в терминал (нижняя панель)
        
        Args:
            message: Текст сообщения
            tag: Тег для цветового выделения (optional)
        """
        def update():
            self.output_text.config(state=tk.NORMAL)
            
            # Проверка лимита буфера
            if self.buffer_lines >= TERMINAL_BUFFER_LINES:
                # Удаляем первую строку
                self.output_text.delete('1.0', '2.0')
                self.buffer_lines -= 1
            
            # Вставка текста
            if tag:
                self.output_text.insert(tk.END, message + '\n', tag)
            else:
                # Попытка определить автоматически по содержанию
                auto_tag = self._detect_message_type(message)
                self.output_text.insert(tk.END, message + '\n', auto_tag)
            
            self.buffer_lines += 1
            self.output_text.see(tk.END)  # Автопрокрутка
            self.output_text.config(state=tk.DISABLED)
        
        # Вызов в главном потоке Tkinter
        self.parent.after(0, update)
    
    def _detect_message_type(self, message: str) -> Optional[str]:
        """Автоопределение типа сообщения по содержанию"""
        if any(emoji in message for emoji in [EMOJI_ERROR, '❌']):
            return 'error'
        elif any(emoji in message for emoji in [EMOJI_SUCCESS, '✅']):
            return 'success'
        elif any(emoji in message for emoji in [EMOJI_WARNING, '⚠️']):
            return 'warning'
        elif any(emoji in message for emoji in [EMOJI_INFO, 'ℹ️', '💡']):
            return 'info'
        return None
    
    def clear_terminal(self):
        """Очистка терминала (только нижняя панель)"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete('1.0', tk.END)
        self.buffer_lines = 0
        self.output_text.config(state=tk.DISABLED)
        self.print_to_terminal("🧹 Терминал очищен")
    
    def run_process(self, command: List[str], use_xterm: bool = True):
        """
        Запуск процесса с захватом вывода
        
        Args:
            command: Список аргументов команды
            use_xterm: Использовать ли xterm (если доступен)
        """
        if self.running:
            self.print_to_terminal("⚠️  Процесс уже запущен!", 'warning')
            return
        
        self.print_to_terminal(f"🚀 Запуск: {' '.join(command)}", 'info')
        
        # Если xterm доступен и требуется его использовать
        if self.xterm_available and use_xterm:
            self._run_with_xterm(command)
        else:
            self._run_with_pty(command)
    
    def _run_with_xterm(self, command: List[str]):
        """Запуск процесса внутри встроенного xterm"""
        try:
            # Получаем Window ID для встраивания xterm
            window_id = self.xterm_frame.winfo_id()
            
            # Запускаем xterm с встраиванием в наш frame
            xterm_cmd = [
                'xterm',
                '-into', str(window_id),
                '-hold',  # Не закрывать после завершения команды
                '-e'
            ] + command
            
            self.process = subprocess.Popen(
                xterm_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            self.running = True
            
            # Запускаем поток для чтения вывода (для нижней панели)
            self.read_thread = threading.Thread(
                target=self._read_process_output_xterm,
                daemon=True
            )
            self.read_thread.start()
            
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка запуска xterm: {e}", 'error')
            self.running = False
    
    def _run_with_pty(self, command: List[str]):
        """Запуск процесса через PTY (полный захват вывода)"""
        try:
            # Создаем PTY
            master_fd, slave_fd = pty.openpty()
            self.master_fd = master_fd
            
            # Запускаем процесс
            self.process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True
            )
            
            # Закрываем slave в родительском процессе
            os.close(slave_fd)
            
            # Устанавливаем неблокирующий режим
            fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
            
            self.running = True
            
            # Запускаем поток для чтения
            self.read_thread = threading.Thread(
                target=self._read_process_output_pty,
                daemon=True
            )
            self.read_thread.start()
            
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка запуска процесса: {e}", 'error')
            self.running = False
    
    def _read_process_output_xterm(self):
        """Чтение вывода процесса запущенного в xterm"""
        try:
            while self.running and self.process:
                # Читаем stderr (stdout идет в xterm)
                if self.process.stderr:
                    line = self.process.stderr.readline()
                    if line:
                        text = line.decode('utf-8', errors='replace').rstrip()
                        if text:
                            self.print_to_terminal(text)
                    elif self.process.poll() is not None:
                        break
        except Exception as e:
            self.print_to_terminal(f"⚠️  Ошибка чтения вывода: {e}", 'warning')
        finally:
            self.running = False
            self.print_to_terminal("📡 Процесс завершен", 'info')
            # Вызываем callback при завершении процесса
            if self.on_process_finished:
                self.parent.after(0, self.on_process_finished)
    
    def _read_process_output_pty(self):
        """Чтение вывода процесса через PTY"""
        try:
            buffer = b''
            last_output_time = 0
            
            while self.running and self.master_fd:
                # Используем select для неблокирующего чтения
                ready, _, _ = select.select([self.master_fd], [], [], 0.05)
                
                if ready:
                    try:
                        data = os.read(self.master_fd, 4096)
                        if not data:
                            break
                        
                        buffer += data
                        current_time = time.time()
                        
                        # Обработка построчно
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            text = line.decode('utf-8', errors='replace').rstrip()
                            
                            # Удаление ANSI escape sequences (опционально)
                            text_clean = self._strip_ansi(text)
                            
                            if text_clean:
                                self.print_to_terminal(text_clean)
                            last_output_time = current_time
                        
                        # Если в буфере есть данные без \n и прошло больше 0.5 сек, выводим
                        if buffer and (current_time - last_output_time > 0.5):
                            text = buffer.decode('utf-8', errors='replace').rstrip()
                            text_clean = self._strip_ansi(text)
                            if text_clean:
                                self.print_to_terminal(text_clean)
                            buffer = b''
                            last_output_time = current_time
                    
                    except OSError:
                        break
                
                # Проверка завершения процесса
                if self.process and self.process.poll() is not None:
                    # Вывести оставшийся буфер
                    if buffer:
                        text = buffer.decode('utf-8', errors='replace').rstrip()
                        text_clean = self._strip_ansi(text)
                        if text_clean:
                            self.print_to_terminal(text_clean)
                    break
        
        except Exception as e:
            self.print_to_terminal(f"⚠️  Ошибка чтения PTY: {e}", 'warning')
        
        finally:
            self.running = False
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except:
                    pass
                self.master_fd = None
            self.print_to_terminal("📡 Процесс завершен", 'info')
            # Вызываем callback при завершении процесса
            if self.on_process_finished:
                self.parent.after(0, self.on_process_finished)
    
    def _strip_ansi(self, text: str) -> str:
        """Удаление ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def stop_process(self):
        """Остановка запущенного процесса"""
        if not self.running or not self.process:
            self.print_to_terminal("ℹ️  Нет запущенного процесса", 'info')
            return
        
        self.print_to_terminal("⏹️  Остановка процесса...", 'warning')
        self.running = False
        
        try:
            # Отправляем SIGTERM группе процессов
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            
            # Ждем завершения (timeout 3 секунды)
            try:
                self.process.wait(timeout=3)
                self.print_to_terminal("✅ Процесс остановлен корректно", 'success')
            except subprocess.TimeoutExpired:
                # Если не завершился - SIGKILL
                self.print_to_terminal("⚠️  Процесс не отвечает, принудительная остановка...", 'warning')
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=1)
                self.print_to_terminal("✅ Процесс принудительно остановлен", 'success')
        
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка остановки процесса: {e}", 'error')
        
        finally:
            self.process = None
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except:
                    pass
                self.master_fd = None
            # Вызываем callback при остановке процесса
            if self.on_process_finished:
                self.parent.after(0, self.on_process_finished)
    
    def _bind_mouse_wheel(self, widget):
        """
        Привязка прокрутки колесиком мыши к виджету
        
        Args:
            widget: Виджет для привязки (обычно ScrolledText или Canvas)
        """
        # Для Linux (X11)
        widget.bind('<Button-4>', lambda e: widget.yview_scroll(-1, 'units'))
        widget.bind('<Button-5>', lambda e: widget.yview_scroll(1, 'units'))
        
        # Для Windows и MacOS
        widget.bind('<MouseWheel>', lambda e: widget.yview_scroll(int(-1 * (e.delta / 120)), 'units'))
    
    def show_input_field(self, show: bool = True):
        """
        Показать/скрыть поле ввода для режима сообщений
        
        Args:
            show: True - показать, False - скрыть
        """
        if hasattr(self, 'input_frame'):
            if show:
                self.input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
                self.input_entry.focus()
            else:
                self.input_frame.pack_forget()
    
    def send_message(self):
        """Отправка сообщения в stdin процесса"""
        if not self.running or not self.process:
            self.print_to_terminal("⚠️  Процесс не запущен!", 'warning')
            return
        
        message = self.input_entry.get().strip()
        if not message:
            return
        
        try:
            # Отправка в stdin процесса
            if self.master_fd:
                # Через PTY
                os.write(self.master_fd, (message + '\n').encode('utf-8'))
            elif self.process.stdin:
                # Через обычный stdin
                self.process.stdin.write((message + '\n').encode('utf-8'))
                self.process.stdin.flush()
            
            # Очистка поля ввода
            self.input_entry.delete(0, tk.END)
            
            # Отображение в терминале
            self.print_to_terminal(f"> {message}", 'info')
        
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка отправки: {e}", 'error')
    
    @property
    def is_running(self) -> bool:
        """Проверка, запущен ли процесс"""
        return self.running and self.process is not None

