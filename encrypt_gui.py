#!/usr/bin/env python3
"""
LightCrypto GUI - Интерфейс шифрования со встроенным терминалом
Запускает tap_encrypt в неймспейсе ns1 во встроенном терминале
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, font
import subprocess
import threading
import os
import sys
import signal
import pty
import select
import fcntl

class EmbeddedTerminal(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.process = None
        self.master_fd = None
        self.is_running = False
        
        self.setup_terminal()
        
    def setup_terminal(self):
        """Настройка встроенного терминала"""
        # Заголовок терминала
        terminal_header = tk.Frame(self)
        terminal_header.pack(fill="x", pady=(0, 5))
        
        tk.Label(terminal_header, text="🖥️ Терминал", font=("Arial", 10, "bold")).pack(side="left")
        
        # Кнопка очистки терминала
        self.clear_btn = tk.Button(
            terminal_header,
            text="Очистить",
            command=self.clear_terminal,
            font=("Arial", 8),
            height=1
        )
        self.clear_btn.pack(side="right")
        
        # Терминал с черным фоном и зеленым текстом
        self.terminal_text = scrolledtext.ScrolledText(
            self,
            height=20,
            width=80,
            bg="black",
            fg="green",
            font=("Consolas", 10),
            wrap=tk.WORD,
            insertbackground="green",
            state=tk.DISABLED
        )
        self.terminal_text.pack(fill="both", expand=True)
        
        # Поле ввода команд
        input_frame = tk.Frame(self)
        input_frame.pack(fill="x", pady=(5, 0))
        
        tk.Label(input_frame, text="$", bg="black", fg="green", font=("Consolas", 10)).pack(side="left")
        
        self.command_entry = tk.Entry(
            input_frame,
            bg="black",
            fg="green",
            font=("Consolas", 10),
            insertbackground="green"
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.command_entry.bind("<Return>", self.execute_command)
        
        # Приветственное сообщение
        self.print_to_terminal("🖥️ LightCrypto встроенный терминал")
        self.print_to_terminal("💡 Введите команду или используйте кнопку 'Запустить задачу'")
        self.print_to_terminal("")
        
    def print_to_terminal(self, text, color="green"):
        """Вывод текста в терминал"""
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.insert(tk.END, text + "\n")
        self.terminal_text.config(state=tk.DISABLED)
        self.terminal_text.see(tk.END)
        self.parent.update_idletasks()
        
    def clear_terminal(self):
        """Очистка терминала"""
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.delete(1.0, tk.END)
        self.terminal_text.config(state=tk.DISABLED)
        self.print_to_terminal("🧹 Терминал очищен")
        
    def execute_command(self, event=None):
        """Выполнение команды из поля ввода"""
        command = self.command_entry.get().strip()
        if not command:
            return
            
        self.command_entry.delete(0, tk.END)
        self.print_to_terminal(f"$ {command}")
        
        # Выполняем команду в отдельном потоке
        thread = threading.Thread(target=self.run_command, args=(command,), daemon=True)
        thread.start()
        
    def run_command(self, command):
        """Выполнение команды в отдельном потоке"""
        try:
            # Запускаем команду через PTY для полного вывода
            master_fd, slave_fd = pty.openpty()
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid
            )
            
            os.close(slave_fd)
            
            # Делаем master_fd неблокирующим
            fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            output_buffer = ""
            
            # Читаем вывод
            while process.poll() is None:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                
                if ready:
                    try:
                        chunk = os.read(master_fd, 1024).decode('utf-8', errors='ignore')
                        if chunk:
                            output_buffer += chunk
                            # Обрабатываем полные строки
                            while '\n' in output_buffer:
                                line, output_buffer = output_buffer.split('\n', 1)
                                clean_line = self.clean_ansi(line)
                                if clean_line.strip():
                                    self.parent.after(0, lambda text=clean_line: self.print_to_terminal(text))
                    except (BlockingIOError, OSError):
                        pass
                        
            # Обрабатываем остатки
            if output_buffer.strip():
                for line in output_buffer.split('\n'):
                    clean_line = self.clean_ansi(line)
                    if clean_line.strip():
                        self.parent.after(0, lambda text=clean_line: self.print_to_terminal(text))
            
            os.close(master_fd)
            
            return_code = process.poll()
            if return_code != 0:
                self.parent.after(0, lambda: self.print_to_terminal(f"❌ Команда завершилась с кодом: {return_code}"))
            else:
                self.parent.after(0, lambda: self.print_to_terminal("✅ Команда выполнена успешно"))
                
        except Exception as e:
            self.parent.after(0, lambda: self.print_to_terminal(f"❌ Ошибка выполнения: {str(e)}"))
            
    def clean_ansi(self, text):
        """Очистка ANSI escape последовательностей"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
        
    def run_tap_encrypt(self, command):
        """Специальный метод для запуска tap_encrypt"""
        self.print_to_terminal("🚀 Запуск LightCrypto Encrypt...")
        self.print_to_terminal(f"📝 Команда: {' '.join(command)}")
        self.print_to_terminal("")
        
        try:
            # Запускаем через PTY для полного вывода
            master_fd, slave_fd = pty.openpty()
            
            self.process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid
            )
            
            os.close(slave_fd)
            self.master_fd = master_fd
            self.is_running = True
            
            # Запускаем чтение вывода
            thread = threading.Thread(target=self.read_tap_output, daemon=True)
            thread.start()
            
        except Exception as e:
            self.print_to_terminal(f"❌ Ошибка запуска: {str(e)}")
            
    def read_tap_output(self):
        """Чтение вывода tap_encrypt"""
        try:
            # Делаем master_fd неблокирующим
            fl = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            output_buffer = ""
            
            while self.process.poll() is None:
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                
                if ready:
                    try:
                        chunk = os.read(self.master_fd, 1024).decode('utf-8', errors='ignore')
                        if chunk:
                            output_buffer += chunk
                            # Обрабатываем полные строки
                            while '\n' in output_buffer:
                                line, output_buffer = output_buffer.split('\n', 1)
                                clean_line = self.clean_ansi(line)
                                if clean_line.strip():
                                    self.parent.after(0, lambda text=clean_line: self.print_to_terminal(text))
                    except (BlockingIOError, OSError):
                        pass
                        
            # Процесс завершился
            return_code = self.process.poll()
            if return_code != 0:
                self.parent.after(0, lambda: self.print_to_terminal(f"❌ Процесс завершился с кодом: {return_code}"))
            else:
                self.parent.after(0, lambda: self.print_to_terminal("✅ Процесс завершился"))
                
        except Exception as e:
            self.parent.after(0, lambda: self.print_to_terminal(f"❌ Ошибка чтения: {str(e)}"))
        finally:
            self.is_running = False
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except:
                    pass
            self.parent.after(0, self.parent.on_process_ended)
            
    def stop_process(self):
        """Остановка процесса"""
        if self.process and self.is_running:
            try:
                self.print_to_terminal("🛑 Остановка процесса...")
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
                
                try:
                    self.process.wait(timeout=3)
                    self.print_to_terminal("✅ Процесс остановлен")
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
                    self.print_to_terminal("🔥 Процесс принудительно завершен")
                    
            except Exception as e:
                self.print_to_terminal(f"❌ Ошибка остановки: {str(e)}")
                
            self.is_running = False
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except:
                    pass

class EncryptGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("encrypt")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # Переменные для полей ввода
        self.ip_var = tk.StringVar(value="192.168.1.2")
        self.port_var = tk.StringVar(value="12345")
        self.message_mode = tk.BooleanVar(value=False)
        
        self.setup_gui()
        self.check_sudo_access()
        
    def setup_gui(self):
        """Создание интерфейса"""
        # Верхняя панель с кнопками
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)
        
        # Кнопка запуска/остановки
        self.start_button = tk.Button(
            top_frame, 
            text="Запустить задачу",
            font=("Arial", 12),
            height=1,
            command=self.toggle_process,
            bg="lightgreen"
        )
        self.start_button.pack(side="left", padx=(0, 10))
        
        # Поля ввода в верхней панели
        tk.Label(top_frame, text="IP:", font=("Arial", 10)).pack(side="left")
        self.ip_entry = tk.Entry(top_frame, textvariable=self.ip_var, font=("Arial", 10), width=15)
        self.ip_entry.pack(side="left", padx=(5, 10))
        
        tk.Label(top_frame, text="Порт:", font=("Arial", 10)).pack(side="left")
        self.port_entry = tk.Entry(top_frame, textvariable=self.port_var, font=("Arial", 10), width=8)
        self.port_entry.pack(side="left", padx=(5, 10))
        
        # Режим сообщений
        self.message_check = tk.Checkbutton(
            top_frame,
            text="Режим сообщений",
            variable=self.message_mode,
            font=("Arial", 10)
        )
        self.message_check.pack(side="left", padx=(10, 0))
        
        # Разделитель
        separator = ttk.Separator(self.root, orient="horizontal")
        separator.pack(fill="x", padx=10, pady=5)
        
        # Встроенный терминал
        self.terminal = EmbeddedTerminal(self.root)
        self.terminal.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
    def check_sudo_access(self):
        """Проверка доступа sudo без пароля"""
        self.terminal.print_to_terminal("🔍 Проверка sudo доступа...")
        
        try:
            result = subprocess.run(
                ["sudo", "-n", "ip", "netns", "list"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                self.terminal.print_to_terminal("✅ Sudo доступ настроен корректно")
                self.terminal.print_to_terminal("🌐 Доступные неймспейсы:")
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        self.terminal.print_to_terminal(f"   {line}")
                else:
                    self.terminal.print_to_terminal("   (неймспейсы не найдены)")
                return True
            else:
                self.terminal.print_to_terminal("❌ Требуется настройка sudo доступа")
                self.terminal.print_to_terminal("💡 Выполните: bash setup_sudo.sh")
                return False
                
        except subprocess.TimeoutExpired:
            self.terminal.print_to_terminal("❌ Sudo запрашивает пароль")
            self.terminal.print_to_terminal("💡 Выполните: bash setup_sudo.sh")
            return False
        except Exception as e:
            self.terminal.print_to_terminal(f"❌ Ошибка проверки sudo: {str(e)}")
            return False
            
    def build_command(self):
        """Построение команды для запуска tap_encrypt"""
        cmd = ["sudo", "ip", "netns", "exec", "ns1", "./build/tap_encrypt"]
        
        if self.message_mode.get():
            cmd.append("--msg")
        
        ip = self.ip_var.get().strip() or "127.0.0.1"
        port = self.port_var.get().strip() or "12345"
        cmd.extend([ip, port])
        
        return cmd
        
    def toggle_process(self):
        """Запуск или остановка процесса"""
        if not self.terminal.is_running:
            self.start_process()
        else:
            self.stop_process()
            
    def start_process(self):
        """Запуск процесса tap_encrypt"""
        if not os.path.exists("./build/tap_encrypt"):
            self.terminal.print_to_terminal("❌ Файл ./build/tap_encrypt не найден")
            self.terminal.print_to_terminal("💡 Выполните сборку: mkdir -p build && cd build && cmake .. && make")
            return
            
        cmd = self.build_command()
        
        self.start_button.config(text="Остановить задачу", bg="red", fg="white")
        
        # Запускаем в терминале
        self.terminal.run_tap_encrypt(cmd)
        
    def stop_process(self):
        """Остановка процесса"""
        self.terminal.stop_process()
        
    def on_process_ended(self):
        """Обработчик завершения процесса"""
        self.start_button.config(text="Запустить задачу", bg="lightgreen", fg="black")
        
    def on_closing(self):
        """Обработчик закрытия окна"""
        if self.terminal.is_running:
            self.terminal.stop_process()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = EncryptGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        if app.terminal.is_running:
            app.terminal.stop_process()
        sys.exit(0)

if __name__ == "__main__":
    main()