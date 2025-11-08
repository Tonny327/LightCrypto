"""
LightCrypto GUI - Встроенный терминал (PyQt6)
Захват вывода процесса через PTY
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QPlainTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCharFormat, QColor, QFont
import subprocess
import threading
import os
import signal
import pty
import select
import fcntl
import re
import time
from typing import List, Optional

from .constants import *


class TerminalReadThread(QThread):
    """Поток для чтения вывода процесса через PTY"""
    
    output_received = pyqtSignal(str)
    process_finished = pyqtSignal()
    
    def __init__(self, master_fd, process):
        super().__init__()
        self.master_fd = master_fd
        self.process = process
        self.running = True
    
    def run(self):
        """Основной цикл чтения"""
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
                            
                            # Удаление ANSI escape sequences
                            text_clean = self._strip_ansi(text)
                            
                            if text_clean:
                                self.output_received.emit(text_clean)
                            last_output_time = current_time
                        
                        # Если в буфере есть данные без \n и прошло больше 0.5 сек, выводим
                        if buffer and (current_time - last_output_time > 0.5):
                            text = buffer.decode('utf-8', errors='replace').rstrip()
                            text_clean = self._strip_ansi(text)
                            if text_clean:
                                self.output_received.emit(text_clean)
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
                            self.output_received.emit(text_clean)
                    break
        
        except Exception as e:
            self.output_received.emit(f"⚠️  Ошибка чтения PTY: {e}")
        
        finally:
            self.running = False
            self.process_finished.emit()
    
    def _strip_ansi(self, text: str) -> str:
        """Удаление ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def stop(self):
        """Остановка потока"""
        self.running = False


class EmbeddedTerminal(QWidget):
    """
    Встроенный терминал для PyQt6
    Захват вывода процесса через PTY
    """
    
    def __init__(self, parent_gui=None):
        """
        Инициализация терминала
        
        Args:
            parent_gui: Ссылка на родительское GUI (для callback)
        """
        super().__init__()
        self.parent_gui = parent_gui
        self.process = None
        self.master_fd = None
        self.read_thread = None
        self.running = False
        self.buffer_lines = 0
        
        # Цветовые форматы
        self._init_text_formats()
        
        # Создание интерфейса
        self._create_widgets()
    
    def _init_text_formats(self):
        """Инициализация цветовых форматов для текста"""
        self.format_error = QTextCharFormat()
        self.format_error.setForeground(QColor('#FF5555'))
        
        self.format_success = QTextCharFormat()
        self.format_success.setForeground(QColor('#50FA7B'))
        
        self.format_warning = QTextCharFormat()
        self.format_warning.setForeground(QColor('#FFB86C'))
        
        self.format_info = QTextCharFormat()
        self.format_info.setForeground(QColor('#8BE9FD'))
        
        self.format_normal = QTextCharFormat()
        self.format_normal.setForeground(QColor('#c9d1d9'))
    
    def _create_widgets(self):
        """Создание элементов интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Заголовок
        header_layout = QHBoxLayout()
        
        label = QLabel("📋 Вывод")
        label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        header_layout.addWidget(label)
        
        header_layout.addStretch()
        
        clear_btn = QPushButton(f"{EMOJI_CLEAN} Очистить")
        clear_btn.clicked.connect(self.clear_terminal)
        clear_btn.setMaximumWidth(150)
        header_layout.addWidget(clear_btn)
        
        layout.addLayout(header_layout)
        
        # Текстовое поле для вывода
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont('Consolas', 10))
        # Увеличиваем минимальную высоту терминала в пикселях
        self.output_text.setMinimumHeight(300)  # Минимальная высота 350px
        self.output_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.output_text)
        
        # Поле ввода для режима сообщений (изначально скрыто)
        self.input_frame = QWidget()
        input_layout = QHBoxLayout(self.input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        input_label = QLabel("💬")
        input_layout.addWidget(input_label)
        
        self.input_entry = QLineEdit()
        self.input_entry.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_entry)
        
        send_btn = QPushButton(f"{EMOJI_SEND} Отправить")
        send_btn.setProperty("class", "success")
        send_btn.clicked.connect(self.send_message)
        send_btn.setMaximumWidth(150)
        input_layout.addWidget(send_btn)
        
        layout.addWidget(self.input_frame)
        self.input_frame.hide()
    
    def print_to_terminal(self, message: str, tag: str = None):
        """
        Вывод сообщения в терминал
        
        Args:
            message: Текст сообщения
            tag: Тег для цветового выделения (optional): 'error', 'success', 'warning', 'info'
        """
        # Проверка лимита буфера
        if self.buffer_lines >= TERMINAL_BUFFER_LINES:
            cursor = self.output_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()  # Удалить символ новой строки
            self.buffer_lines -= 1
        
        # Определение формата
        if tag == 'error':
            fmt = self.format_error
        elif tag == 'success':
            fmt = self.format_success
        elif tag == 'warning':
            fmt = self.format_warning
        elif tag == 'info':
            fmt = self.format_info
        else:
            # Автоопределение по содержанию
            fmt = self._detect_message_format(message)
        
        # Вставка текста
        cursor = self.output_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.setCharFormat(fmt)
        cursor.insertText(message + '\n')
        
        self.buffer_lines += 1
        
        # Автопрокрутка
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _detect_message_format(self, message: str) -> QTextCharFormat:
        """Автоопределение формата сообщения по содержанию"""
        if any(emoji in message for emoji in [EMOJI_ERROR, '❌']):
            return self.format_error
        elif any(emoji in message for emoji in [EMOJI_SUCCESS, '✅']):
            return self.format_success
        elif any(emoji in message for emoji in [EMOJI_WARNING, '⚠️']):
            return self.format_warning
        elif any(emoji in message for emoji in [EMOJI_INFO, 'ℹ️', '💡']):
            return self.format_info
        return self.format_normal
    
    def clear_terminal(self):
        """Очистка терминала"""
        self.output_text.clear()
        self.buffer_lines = 0
        self.print_to_terminal("🧹 Терминал очищен", 'info')
    
    def run_process(self, command: List[str], use_xterm: bool = True):
        """
        Запуск процесса с захватом вывода
        
        Args:
            command: Список аргументов команды
            use_xterm: Использовать ли xterm (игнорируется, всегда PTY)
        """
        if self.running:
            self.print_to_terminal("⚠️  Процесс уже запущен!", 'warning')
            return
        
        self.print_to_terminal(f"🚀 Запуск: {' '.join(command)}", 'info')
        self._run_with_pty(command)
    
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
            self.read_thread = TerminalReadThread(master_fd, self.process)
            self.read_thread.output_received.connect(self.print_to_terminal)
            self.read_thread.process_finished.connect(self._on_process_finished)
            self.read_thread.start()
            
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка запуска процесса: {e}", 'error')
            self.running = False
    
    def _on_process_finished(self):
        """Обработка завершения процесса"""
        self.running = False
        self.print_to_terminal("📡 Процесс завершен", 'info')
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None
        if self.parent_gui and hasattr(self.parent_gui, 'on_terminal_process_finished'):
            try:
                self.parent_gui.on_terminal_process_finished()
            except Exception as exc:
                self.print_to_terminal(f"⚠️  Ошибка post-stop callback: {exc}", 'warning')
    
    def stop_process(self):
        """Остановка запущенного процесса"""
        if not self.running or not self.process:
            self.print_to_terminal("ℹ️  Нет запущенного процесса", 'info')
            return
        
        self.print_to_terminal("⏹️  Остановка процесса...", 'warning')
        self.running = False
        
        # Остановка потока чтения
        if self.read_thread:
            self.read_thread.stop()
            self.read_thread.wait(1000)  # Ждем до 1 секунды
        
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
    
    def show_input_field(self, show: bool = True):
        """
        Показать/скрыть поле ввода для режима сообщений
        
        Args:
            show: True - показать, False - скрыть
        """
        if show:
            self.input_frame.show()
            self.input_entry.setFocus()
        else:
            self.input_frame.hide()
    
    def send_message(self):
        """Отправка сообщения в stdin процесса"""
        if not self.running or not self.process:
            self.print_to_terminal("⚠️  Процесс не запущен!", 'warning')
            return
        
        message = self.input_entry.text().strip()
        if not message:
            return
        
        try:
            # Отправка в stdin процесса через PTY
            if self.master_fd:
                os.write(self.master_fd, (message + '\n').encode('utf-8'))
            
            # Очистка поля ввода
            self.input_entry.clear()
            
            # Отображение в терминале
            self.print_to_terminal(f"> {message}", 'info')
        
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка отправки: {e}", 'error')
    
    @property
    def is_running(self) -> bool:
        """Проверка, запущен ли процесс"""
        return self.running and self.process is not None

