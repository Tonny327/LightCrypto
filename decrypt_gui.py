#!/usr/bin/env python3
"""
LightCrypto GUI - Интерфейс расшифровки
Запускает tap_decrypt в неймспейсе ns2
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import queue
import os
import sys
import time
import pty
import select

class DecryptGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("decrypt")
        self.root.geometry("500x600")
        self.root.resizable(True, True)
        
        # Переменные для процесса
        self.process = None
        self.output_queue = queue.Queue()
        self.is_running = False
        
        # Переменные для полей ввода
        self.ip_var = tk.StringVar(value="192.168.1.2")
        self.port_var = tk.StringVar(value="12345")
        self.message_mode = tk.BooleanVar(value=False)
        
        self.setup_gui()
        self.check_sudo_access()
        
    def setup_gui(self):
        """Создание интерфейса"""
        # Кнопка запуска/остановки
        self.start_button = tk.Button(
            self.root, 
            text="Запустить задачу",
            font=("Arial", 12),
            height=2,
            command=self.toggle_process
        )
        self.start_button.pack(pady=10, padx=20, fill="x")
        
        # Разделитель
        separator1 = ttk.Separator(self.root, orient="horizontal")
        separator1.pack(fill="x", padx=20, pady=5)
        
        # Консоль
        console_frame = tk.Frame(self.root)
        console_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        console_label = tk.Label(console_frame, text="Консоль", font=("Arial", 10, "bold"))
        console_label.pack(anchor="w")
        
        # Текстовое поле консоли с белым фоном и черным текстом
        self.console_text = scrolledtext.ScrolledText(
            console_frame,
            height=15,
            width=60,
            bg="white",
            fg="black",
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.console_text.pack(fill="both", expand=True)
        
        # Разделитель
        separator2 = ttk.Separator(self.root, orient="horizontal")
        separator2.pack(fill="x", padx=20, pady=5)
        
        # Поля ввода
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10, padx=20, fill="x")
        
        # IP адрес
        ip_label = tk.Label(input_frame, text="Введите IP. По умолчанию 0.0.0.0 (слушать все)")
        ip_label.pack(anchor="w")
        
        self.ip_entry = tk.Entry(input_frame, textvariable=self.ip_var, font=("Arial", 10))
        self.ip_entry.pack(fill="x", pady=(0, 10))
        
        # Порт
        port_label = tk.Label(input_frame, text="Введите порт. По умолчанию 12345")
        port_label.pack(anchor="w")
        
        self.port_entry = tk.Entry(input_frame, textvariable=self.port_var, font=("Arial", 10))
        self.port_entry.pack(fill="x", pady=(0, 10))
        
        # Режим сообщений
        self.message_check = tk.Checkbutton(
            input_frame,
            text="☐ Режим приема текстовых сообщений",
            variable=self.message_mode,
            font=("Arial", 10)
        )
        self.message_check.pack(anchor="w")
        
        # Запуск проверки вывода
        self.root.after(50, self.process_output)
        
    def check_sudo_access(self):
        """Проверка доступа sudo без пароля"""
        self.console_text.insert(tk.END, "🔍 Проверка sudo доступа...\n")
        self.console_text.see(tk.END)
        
        try:
            # Проверяем доступ к ip netns
            result = subprocess.run(
                ["sudo", "-n", "ip", "netns", "list"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                self.console_text.insert(tk.END, "✅ Sudo доступ настроен корректно\n")
                self.console_text.insert(tk.END, "🌐 Доступные неймспейсы:\n")
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        self.console_text.insert(tk.END, f"   {line}\n")
                else:
                    self.console_text.insert(tk.END, "   (неймспейсы не найдены)\n")
                return True
            else:
                self.console_text.insert(tk.END, "❌ Требуется настройка sudo доступа\n")
                self.console_text.insert(tk.END, "💡 Выполните: bash setup_sudo.sh\n")
                return False
                
        except subprocess.TimeoutExpired:
            self.console_text.insert(tk.END, "❌ Sudo запрашивает пароль\n")
            self.console_text.insert(tk.END, "💡 Выполните: bash setup_sudo.sh\n")
            return False
        except Exception as e:
            self.console_text.insert(tk.END, f"❌ Ошибка проверки sudo: {str(e)}\n")
            return False
        finally:
            self.console_text.see(tk.END)
            
    def build_command(self):
        """Построение команды для запуска tap_decrypt"""
        cmd = ["sudo", "ip", "netns", "exec", "ns2", "./build/tap_decrypt"]
        
        # Если включен режим сообщений
        if self.message_mode.get():
            cmd.append("--msg")
        
        # Добавляем IP и порт
        # Для decrypt программы: первый аргумент может быть портом или IP+портом
        ip = self.ip_var.get().strip()
        port = self.port_var.get().strip() or "12345"
        
        # tap_decrypt принимает аргументы по-разному:
        # - если один аргумент: это порт (слушает 0.0.0.0:порт)
        # - если два аргумента: IP и порт
        if not ip or ip == "0.0.0.0":
            cmd.append(port)  # только порт
        else:
            cmd.extend([ip, port])  # IP и порт
        
        return cmd
        
    def toggle_process(self):
        """Запуск или остановка процесса"""
        if not self.is_running:
            self.start_process()
        else:
            self.stop_process()
            
    def start_process(self):
        """Запуск процесса tap_decrypt"""
        # Проверяем существование исполняемого файла
        if not os.path.exists("./build/tap_decrypt"):
            self.console_text.insert(tk.END, "❌ Файл ./build/tap_decrypt не найден\n")
            self.console_text.insert(tk.END, "💡 Выполните сборку: mkdir -p build && cd build && cmake .. && make\n")
            self.console_text.see(tk.END)
            return
            
        cmd = self.build_command()
        
        # Показываем команду в консоли
        self.console_text.insert(tk.END, f"\n{'='*50}\n")
        self.console_text.insert(tk.END, f"🚀 Запуск команды: {' '.join(cmd)}\n")
        self.console_text.insert(tk.END, f"{'='*50}\n")
        self.console_text.see(tk.END)
        
        try:
            # Создаем окружение для разблокировки буферизации
            env = os.environ.copy()
            env.update({
                'PYTHONUNBUFFERED': '1',
                'LC_ALL': 'C.UTF-8',
                'TERM': 'xterm'  # Эмулируем терминал
            })
            
            # Используем pty для эмуляции терминала - это заставляет программы
            # выводить данные немедленно, как если бы они были в интерактивном режиме
            master_fd, slave_fd = pty.openpty()
            
            self.process = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                preexec_fn=os.setsid  # Создаем новую группу процессов
            )
            
            # Закрываем slave_fd в родительском процессе
            os.close(slave_fd)
            
            # Сохраняем master_fd для чтения
            self.master_fd = master_fd
            
            self.console_text.insert(tk.END, "🔧 Используем PTY для эмуляции терминала\n")
            
            self.is_running = True
            self.start_button.config(text="Остановить задачу", bg="red", fg="white")
            
            # Запускаем поток для чтения вывода
            output_thread = threading.Thread(target=self.read_output)
            output_thread.daemon = True
            output_thread.start()
            
        except Exception as e:
            self.console_text.insert(tk.END, f"❌ Ошибка запуска: {str(e)}\n")
            self.console_text.see(tk.END)
            
    def stop_process(self):
        """Остановка процесса"""
        if self.process:
            try:
                # Завершаем всю группу процессов
                os.killpg(os.getpgid(self.process.pid), 15)  # SIGTERM
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.process.pid), 9)  # SIGKILL
                except:
                    self.process.kill()
            except Exception as e:
                self.console_text.insert(tk.END, f"❌ Ошибка остановки: {str(e)}\n")
                
        # Закрываем master_fd если он есть
        if hasattr(self, 'master_fd'):
            try:
                os.close(self.master_fd)
            except:
                pass
                
        self.is_running = False
        self.process = None
        self.start_button.config(text="Запустить задачу", bg="SystemButtonFace", fg="black")
        
        self.console_text.insert(tk.END, "\n🛑 Процесс остановлен\n")
        self.console_text.see(tk.END)
        
    def read_output(self):
        """Чтение вывода процесса в отдельном потоке через PTY"""
        if not self.process or not hasattr(self, 'master_fd'):
            return
            
        try:
            import fcntl
            
            # Делаем master_fd неблокирующим
            fl = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            output_buffer = ""
            
            # Читаем вывод из PTY
            while self.process.poll() is None:
                # Проверяем доступность данных для чтения
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                
                if ready:
                    try:
                        chunk = os.read(self.master_fd, 1024).decode('utf-8', errors='ignore')
                        if chunk:
                            output_buffer += chunk
                            # Обрабатываем полные строки
                            while '\n' in output_buffer:
                                line, output_buffer = output_buffer.split('\n', 1)
                                # Очищаем от управляющих символов терминала
                                clean_line = self.clean_terminal_output(line)
                                if clean_line.strip():
                                    self.output_queue.put(clean_line.rstrip())
                    except (BlockingIOError, OSError):
                        # Нет данных для чтения
                        pass
                else:
                    # Небольшая пауза
                    time.sleep(0.01)
                    
            # Обрабатываем остатки буфера
            if output_buffer.strip():
                for line in output_buffer.split('\n'):
                    clean_line = self.clean_terminal_output(line)
                    if clean_line.strip():
                        self.output_queue.put(clean_line.strip())
                    
            # Процесс завершился
            return_code = self.process.poll()
            if return_code != 0:
                self.output_queue.put(f"❌ Процесс завершился с кодом: {return_code}")
            else:
                self.output_queue.put("✅ Процесс завершился успешно")
                
            self.output_queue.put("PROCESS_ENDED")
                
        except Exception as e:
            self.output_queue.put(f"❌ Ошибка чтения вывода: {str(e)}")
            self.output_queue.put("PROCESS_ENDED")
        finally:
            # Закрываем master_fd
            if hasattr(self, 'master_fd'):
                try:
                    os.close(self.master_fd)
                except:
                    pass
                    
    def clean_terminal_output(self, line):
        """Очистка строки от управляющих символов терминала"""
        import re
        # Удаляем ANSI escape последовательности
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', line)
            
    def process_output(self):
        """Обработка вывода из очереди"""
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line == "PROCESS_ENDED":
                    self.is_running = False
                    self.process = None
                    self.start_button.config(text="Запустить задачу", bg="SystemButtonFace", fg="black")
                    break
                else:
                    self.console_text.insert(tk.END, line + "\n")
                    self.console_text.see(tk.END)
        except queue.Empty:
            pass
            
        # Планируем следующую проверку (чаще для лучшей отзывчивости)
        self.root.after(50, self.process_output)
        
    def on_closing(self):
        """Обработчик закрытия окна"""
        if self.is_running:
            self.stop_process()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = DecryptGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        if app.is_running:
            app.stop_process()
        sys.exit(0)

if __name__ == "__main__":
    main()
