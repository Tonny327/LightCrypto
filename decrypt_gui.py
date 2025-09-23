#!/usr/bin/env python3
"""
LightCrypto GUI - Интерфейс расшифровки со встроенным терминалом
Запускает tap_decrypt в неймспейсе ns2 во встроенном терминале
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
import shutil

class EmbeddedTerminal(tk.Frame):
    def __init__(self, parent_widget, parent_gui):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget  # tkinter родитель
        self.parent_gui = parent_gui        # GUI класс с методами
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
        
        # Терминал с белым фоном и черным текстом
        self.terminal_text = scrolledtext.ScrolledText(
            self,
            height=20,
            width=80,
            bg="white",
            fg="black",
            font=("Consolas", 10),
            wrap=tk.WORD,
            insertbackground="black",
            state=tk.DISABLED
        )
        self.terminal_text.pack(fill="both", expand=True)
        
        # Поле ввода команд
        input_frame = tk.Frame(self)
        input_frame.pack(fill="x", pady=(5, 0))
        
        tk.Label(input_frame, text="$", bg="white", fg="black", font=("Consolas", 10)).pack(side="left")
        
        self.command_entry = tk.Entry(
            input_frame,
            bg="white",
            fg="black",
            font=("Consolas", 10),
            insertbackground="black"
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.command_entry.bind("<Return>", self.execute_command)
        
        # Приветственное сообщение
        self.print_to_terminal("🖥️ LightCrypto встроенный терминал")
        self.print_to_terminal("💡 Введите команду или используйте кнопку 'Запустить задачу'")
        self.print_to_terminal("")
        
    def print_to_terminal(self, text, color="black"):
        """Вывод текста в терминал"""
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.insert(tk.END, text + "\n")
        self.terminal_text.config(state=tk.DISABLED)
        self.terminal_text.see(tk.END)
        self.parent_widget.update_idletasks()
        
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
                                    self.parent_widget.after(0, lambda text=clean_line: self.print_to_terminal(text))
                    except (BlockingIOError, OSError):
                        pass
                        
            # Обрабатываем остатки
            if output_buffer.strip():
                for line in output_buffer.split('\n'):
                    clean_line = self.clean_ansi(line)
                    if clean_line.strip():
                        self.parent_widget.after(0, lambda text=clean_line: self.print_to_terminal(text))
            
            os.close(master_fd)
            
            return_code = process.poll()
            if return_code != 0:
                self.parent_widget.after(0, lambda: self.print_to_terminal(f"❌ Команда завершилась с кодом: {return_code}"))
            else:
                self.parent_widget.after(0, lambda: self.print_to_terminal("✅ Команда выполнена успешно"))
                
        except Exception as e:
            self.parent_widget.after(0, lambda: self.print_to_terminal(f"❌ Ошибка выполнения: {str(e)}"))
            
    def clean_ansi(self, text):
        """Очистка ANSI escape последовательностей"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
        
    def run_tap_decrypt(self, command):
        """Специальный метод для запуска tap_decrypt"""
        self.print_to_terminal("🚀 Запуск LightCrypto Decrypt...")
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
        """Чтение вывода tap_decrypt"""
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
                                    self.parent_widget.after(0, lambda text=clean_line: self.print_to_terminal(text))
                    except (BlockingIOError, OSError):
                        pass
                        
            # Процесс завершился
            return_code = self.process.poll()
            if return_code != 0:
                self.parent_widget.after(0, lambda: self.print_to_terminal(f"❌ Процесс завершился с кодом: {return_code}"))
            else:
                self.parent_widget.after(0, lambda: self.print_to_terminal("✅ Процесс завершился"))
                
        except Exception as e:
            self.parent_widget.after(0, lambda: self.print_to_terminal(f"❌ Ошибка чтения: {str(e)}"))
        finally:
            self.is_running = False
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except:
                    pass
            self.parent_widget.after(0, self.parent_gui.on_process_ended)
            
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
        
        # ПРИНУДИТЕЛЬНО сбрасываем все состояния независимо от условий
        self.is_running = False
        self.process = None
        if self.master_fd:
            try:
                os.close(self.master_fd)
                self.master_fd = None
            except:
                pass
        
        # Уведомляем родительский класс о завершении процесса
        self.parent_widget.after(0, self.parent_gui.on_process_ended)

class DecryptGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("decrypt")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # Переменные для полей ввода
        self.ip_var = tk.StringVar(value="192.168.1.2")
        self.port_var = tk.StringVar(value="12345")
        self.message_mode = tk.BooleanVar(value=False)
        self.network_mode = tk.BooleanVar(value=False)  # False = локальный, True = сетевой
        self.use_embedded_xterm = tk.BooleanVar(value=True)
        self._xterm_proc = None
        self._xterm_container = None
        
        self.setup_gui()
        self.check_sudo_access()
        
    def setup_gui(self):
        """Создание интерфейса"""
        # Верхняя панель с кнопками (2 строки)
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)
        top_row1 = tk.Frame(top_frame)
        top_row1.pack(fill="x")
        top_row2 = tk.Frame(top_frame)
        top_row2.pack(fill="x", pady=(4, 0))

        # Кнопка запуска/остановки
        self.start_button = tk.Button(
            top_row1, 
            text="Запустить задачу",
            font=("Arial", 12),
            height=1,
            command=self.toggle_process,
            bg="lightblue"
        )
        self.start_button.pack(side="left", padx=(0, 10))

        # Кнопки управления неймспейсами
        ns_btn_frame = tk.Frame(top_row2)
        ns_btn_frame.pack(side="left", padx=(0, 10))
        self.ns_setup_btn = tk.Button(
            ns_btn_frame,
            text="Создать неймспейсы",
            font=("Arial", 9),
            command=self.setup_namespaces,
            bg="#eef6ff"
        )
        self.ns_setup_btn.pack(side="left")
        self.ns_cleanup_btn = tk.Button(
            ns_btn_frame,
            text="Очистить",
            font=("Arial", 9),
            command=self.cleanup_namespaces,
            bg="#ffecec"
        )
        self.ns_cleanup_btn.pack(side="left", padx=(5, 0))
        
        # Переключатель режимов
        mode_frame = tk.Frame(top_row1)
        mode_frame.pack(side="left", padx=(0, 10))
        tk.Label(mode_frame, text="Режим:", font=("Arial", 10, "bold")).pack()
        mode_radio_frame = tk.Frame(mode_frame)
        mode_radio_frame.pack()
        self.local_radio = tk.Radiobutton(
            mode_radio_frame,
            text="Локальный",
            variable=self.network_mode,
            value=False,
            command=self.on_mode_change,
            font=("Arial", 9)
        )
        self.local_radio.pack(side="left")
        self.network_radio = tk.Radiobutton(
            mode_radio_frame,
            text="Сетевой",
            variable=self.network_mode,
            value=True,
            command=self.on_mode_change,
            font=("Arial", 9)
        )
        self.network_radio.pack(side="left")

        # Поля ввода в верхней панели
        tk.Label(top_row1, text="IP:", font=("Arial", 10)).pack(side="left")
        self.ip_entry = tk.Entry(top_row1, textvariable=self.ip_var, font=("Arial", 10), width=15)
        self.ip_entry.pack(side="left", padx=(5, 10))
        
        tk.Label(top_row1, text="Порт:", font=("Arial", 10)).pack(side="left")
        self.port_entry = tk.Entry(top_row1, textvariable=self.port_var, font=("Arial", 10), width=8)
        self.port_entry.pack(side="left", padx=(5, 10))
        
        # Режим сообщений
        self.message_check = tk.Checkbutton(
            top_row2,
            text="Режим сообщений",
            variable=self.message_mode,
            font=("Arial", 10),
            command=self.on_message_mode_change
        )
        self.message_check.pack(side="left", padx=(10, 0))

        # Встроенный Xterm (X11)
        self.xterm_check = tk.Checkbutton(
            top_row2,
            text="Встроенный xterm (X11)",
            variable=self.use_embedded_xterm,
            font=("Arial", 10),
            command=self.on_xterm_toggle
        )
        self.xterm_check.pack(side="left", padx=(10, 0))
        
        # Разделитель
        separator = ttk.Separator(self.root, orient="horizontal")
        separator.pack(fill="x", padx=10, pady=5)
        
        # Встроенный терминал
        self.terminal = EmbeddedTerminal(self.root, self)
        self.terminal.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        # Включаем xterm по умолчанию (если доступен)
        self.on_xterm_toggle()

        # Панель сервисов (iperf/tcpdump)
        svc_frame = tk.Frame(self.root)
        svc_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(svc_frame, text="Сервисы:", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 10))

        self.iperf_tcp_server_btn = tk.Button(svc_frame, text="iperf TCP сервер", font=("Arial", 9), command=self.run_iperf_tcp_server)
        self.iperf_tcp_server_btn.pack(side="left")

        self.iperf_udp_server_btn = tk.Button(svc_frame, text="iperf UDP сервер", font=("Arial", 9), command=self.run_iperf_udp_server)
        self.iperf_udp_server_btn.pack(side="left", padx=(5, 0))

        self.tcpdump_tap_btn = tk.Button(svc_frame, text="tcpdump tap", font=("Arial", 9), command=self.run_tcpdump_tap)
        self.tcpdump_tap_btn.pack(side="left", padx=(5, 0))
        
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
        """Построение команды для запуска tap_decrypt"""
        if self.network_mode.get():
            # Сетевой режим - запуск без неймспейса
            cmd = ["sudo", "./build/tap_decrypt"]
        else:
            # Локальный режим - запуск в неймспейсе ns2
            cmd = ["sudo", "ip", "netns", "exec", "ns2", "./build/tap_decrypt"]

        if self.message_mode.get():
            cmd.append("--msg")

        ip = self.ip_var.get().strip()
        port = self.port_var.get().strip() or "12345"

        # Поведение соответствует README:
        # - В сетевом режиме приемник может слушать на 0.0.0.0 или только порт
        # - Если IP пустой, используем только порт (эквивалент "--msg 5555" или "5555")
        if not ip:
            cmd.append(port)
        else:
            cmd.extend([ip, port])

        return cmd
        
    def toggle_process(self):
        """Запуск или остановка процесса"""
        if not self.terminal.is_running:
            self.start_process()
        else:
            self.stop_process()
            
    def start_process(self):
        """Запуск процесса tap_decrypt"""
        if not os.path.exists("./build/tap_decrypt"):
            self.terminal.print_to_terminal("❌ Файл ./build/tap_decrypt не найден")
            self.terminal.print_to_terminal("💡 Выполните сборку: mkdir -p build && cd build && cmake .. && make")
            return
            
        cmd = self.build_command()
        
        self.start_button.config(text="Остановить задачу", bg="red", fg="white")
        
        if self.use_embedded_xterm.get() and shutil.which("xterm") and os.environ.get("DISPLAY"):
            # Запуск во встроенном xterm
            command_str = " ".join(cmd)
            self._launch_embedded_xterm("tap_decrypt", command_str)
        else:
            # Запускаем во встроенном текстовом терминале Tk
            self.terminal.run_tap_decrypt(cmd)
            
    def stop_process(self):
        """Остановка процесса"""
        self.terminal.stop_process()
        self._stop_embedded_xterm()
        # Принудительно сбрасываем состояние кнопки
        self.start_button.config(text="Запустить задачу", bg="lightblue", fg="black")
        
    def on_process_ended(self):
        """Обработчик завершения процесса"""
        self.start_button.config(text="Запустить задачу", bg="lightblue", fg="black")
        # Закрываем встроенный xterm, если был запущен
        self._stop_embedded_xterm()

    def on_mode_change(self):
        """Обработчик изменения режима работы (локальный/сетевой)"""
        if self.network_mode.get():
            self.terminal.print_to_terminal("🌐 Переключен сетевой режим")
            self.terminal.print_to_terminal("📡 Команда: sudo ./build/tap_decrypt [IP|PORT]")
            self.terminal.print_to_terminal("💡 Пример: sudo ./build/tap_decrypt 0.0.0.0 5555 или sudo ./build/tap_decrypt 5555")
        else:
            self.terminal.print_to_terminal("🏠 Переключен локальный режим")
            self.terminal.print_to_terminal("📡 Команда: sudo ip netns exec ns2 ./build/tap_decrypt IP PORT")
            self.terminal.print_to_terminal("💡 Для тестирования на одном компьютере с неймспейсами")

    def on_message_mode_change(self):
        """Обработчик изменения режима сообщений"""
        if self.message_mode.get():
            self.terminal.print_to_terminal("💬 Режим сообщений включен")
            # Отключаем сервисы Ethernet-трафика
            for btn in [self.iperf_tcp_server_btn, self.iperf_udp_server_btn, self.tcpdump_tap_btn]:
                btn.config(state=tk.DISABLED)
            self.terminal.print_to_terminal("⛔ iperf/tcpdump отключены в режиме сообщений")
        else:
            self.terminal.print_to_terminal("🔧 Режим сообщений отключен")
            for btn in [self.iperf_tcp_server_btn, self.iperf_udp_server_btn, self.tcpdump_tap_btn]:
                btn.config(state=tk.NORMAL)

    def on_xterm_toggle(self):
        """Показать/скрыть контейнер для встроенного xterm"""
        if self.use_embedded_xterm.get():
            if not os.environ.get("DISPLAY"):
                self.terminal.print_to_terminal("❌ DISPLAY не установлен. X11 недоступен")
                self.use_embedded_xterm.set(False)
                return
            if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
                self.terminal.print_to_terminal("❌ Wayland без XWayland — встроенный xterm недоступен")
                self.use_embedded_xterm.set(False)
                return
            if not shutil.which("xterm"):
                self.terminal.print_to_terminal("❌ xterm не найден. Установите пакет xterm")
                self.use_embedded_xterm.set(False)
                return
            if self._xterm_container is None:
                self._xterm_container = tk.Frame(self.root, height=480, bg="black")
            # Вставляем контейнер над встроенным лог-терминалом
            self._xterm_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.terminal.print_to_terminal("🪟 Встроенный xterm включён")
        else:
            self._stop_embedded_xterm()
            if self._xterm_container is not None:
                self._xterm_container.pack_forget()
                self.terminal.print_to_terminal("🪟 Встроенный xterm выключен")

    # --- Сервисы для тестирования (в соответствии с README) ---
    def _find_terminal_emulator(self):
        for name in ["gnome-terminal", "konsole", "xterm", "x-terminal-emulator"]:
            if shutil.which(name):
                return name
        return None

    def _open_external_terminal(self, title, command_str):
        term = self._find_terminal_emulator()
        if not term:
            # fallback — выполним внутри встроенного терминала
            threading.Thread(target=self.terminal.run_command, args=(command_str,), daemon=True).start()
            return
        try:
            if term == "gnome-terminal":
                subprocess.Popen(["gnome-terminal", "--title", title, "--", "bash", "-lc", f"{command_str}; echo; read -p 'Нажмите Enter для закрытия...'"], preexec_fn=os.setsid)
            elif term == "konsole":
                subprocess.Popen(["konsole", "-p", f"tabtitle={title}", "-e", "bash", "-lc", f"{command_str}; echo; read -p 'Enter...'"], preexec_fn=os.setsid)
            else:
                subprocess.Popen([term, "-T", title, "-e", "bash", "-lc", f"{command_str}; echo; read -p 'Enter...'"], preexec_fn=os.setsid)
        except Exception:
            threading.Thread(target=self.terminal.run_command, args=(command_str,), daemon=True).start()

    def _ns_or_local_prefix(self):
        # Для приемника: команды выполняются в ns2 в локальном режиме
        if self.network_mode.get():
            return []
        return ["sudo", "ip", "netns", "exec", "ns2"]

    def run_iperf_tcp_server(self):
        if self.message_mode.get():
            self.terminal.print_to_terminal("⚠️ Режим сообщений активен — iperf TCP сервер недоступен")
            return
        cmd = "sudo ip netns exec ns2 iperf -s -B 10.0.0.2"
        self.terminal.print_to_terminal("🛰 Открываю iperf TCP сервер ns2 на 10.0.0.2...")
        self._open_external_terminal("iperf TCP server (ns2)", cmd)

    def run_iperf_udp_server(self):
        if self.message_mode.get():
            self.terminal.print_to_terminal("⚠️ Режим сообщений активен — iperf UDP сервер недоступен")
            return
        cmd = "sudo ip netns exec ns2 iperf -s -u -B 10.0.0.2"
        self.terminal.print_to_terminal("🛰 Открываю iperf UDP сервер ns2 на 10.0.0.2...")
        self._open_external_terminal("iperf UDP server (ns2)", cmd)

    def run_tcpdump_tap(self):
        if self.message_mode.get():
            self.terminal.print_to_terminal("⚠️ Режим сообщений активен — tcpdump недоступен")
            return
        # В README интерфейс tap1 в ns2
        if self.network_mode.get():
            self.terminal.print_to_terminal("ℹ️ tcpdump для сетевого режима настрой вручную (нет неймспейса)")
            return
        cmd = "sudo ip netns exec ns2 tcpdump -i tap1 -v"
        self.terminal.print_to_terminal("🔎 Открываю tcpdump на ns2/tap1...")
        self._open_external_terminal("tcpdump ns2/tap1", cmd)
        
    def on_closing(self):
        """Обработчик закрытия окна"""
        if self.terminal.is_running:
            self.terminal.stop_process()
        self._stop_embedded_xterm()
        self.root.destroy()

    # --- Встроенный xterm ---
    def _launch_embedded_xterm(self, title, command_str):
        try:
            self._stop_embedded_xterm()
            if self._xterm_container is None:
                self._xterm_container = tk.Frame(self.root, height=480, bg="black")
                self._xterm_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            win_id = self._xterm_container.winfo_id()
            full_cmd = [
                "xterm",
                "-into", str(win_id),
                "-T", title,
                "-fa", "Monospace",
                "-fs", "10",
                "-e", "bash", "-lc",
                f"{command_str}; echo; read -p 'Нажмите Enter для закрытия...'"
            ]
            self._xterm_proc = subprocess.Popen(full_cmd, preexec_fn=os.setsid)
            self.terminal.print_to_terminal(f"🚀 xterm: {title} запущен")
        except Exception as e:
            self.terminal.print_to_terminal(f"❌ Не удалось запустить встроенный xterm: {e}")
            self.use_embedded_xterm.set(False)

    def _stop_embedded_xterm(self):
        if self._xterm_proc is not None:
            try:
                pgid = os.getpgid(self._xterm_proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                pass
            self._xterm_proc = None

    def setup_namespaces(self):
        """Создание неймспейсов и интерфейсов по README"""
        cmds = [
            "sudo ip netns delete ns1 2>/dev/null",
            "sudo ip netns delete ns2 2>/dev/null",
            "sudo killall tap_encrypt tap_decrypt tcpdump 2>/dev/null || true",
            "sudo ip netns add ns1",
            "sudo ip netns add ns2",
            "sudo ip netns exec ns1 ip tuntap add dev tap0 mode tap",
            "sudo ip netns exec ns1 ip addr add 10.0.0.1/24 dev tap0",
            "sudo ip netns exec ns1 ip link set tap0 up",
            "sudo ip netns exec ns2 ip tuntap add dev tap1 mode tap",
            "sudo ip netns exec ns2 ip addr add 10.0.0.2/24 dev tap1",
            "sudo ip netns exec ns2 ip link set tap1 up",
            "sudo ip link add veth1 type veth peer name veth2",
            "sudo ip link set veth1 netns ns1",
            "sudo ip link set veth2 netns ns2",
            "sudo ip netns exec ns1 ip addr add 192.168.1.1/24 dev veth1",
            "sudo ip netns exec ns1 ip link set veth1 up",
            "sudo ip netns exec ns2 ip addr add 192.168.1.2/24 dev veth2",
            "sudo ip netns exec ns2 ip link set veth2 up",
            "sudo ip netns exec ns1 ip route add default via 192.168.1.2 || true",
            "sudo ip netns exec ns2 ip route add default via 192.168.1.1 || true",
            "sudo ip netns exec ns1 sysctl -w net.ipv6.conf.all.disable_ipv6=1",
            "sudo ip netns exec ns2 sysctl -w net.ipv6.conf.all.disable_ipv6=1"
        ]
        full_cmd = " && ".join(cmds)
        self.terminal.print_to_terminal("🔧 Настраиваем неймспейсы по README...")
        threading.Thread(target=self.terminal.run_command, args=(full_cmd,), daemon=True).start()

    def cleanup_namespaces(self):
        """Удаление неймспейсов и остановка процессов"""
        cmds = [
            "sudo ip netns delete ns1 2>/dev/null",
            "sudo ip netns delete ns2 2>/dev/null",
            "sudo killall tap_encrypt tap_decrypt tcpdump 2>/dev/null || true"
        ]
        full_cmd = " && ".join(cmds)
        self.terminal.print_to_terminal("🧹 Очищаем ресурсы...")
        threading.Thread(target=self.terminal.run_command, args=(full_cmd,), daemon=True).start()

def main():
    root = tk.Tk()
    app = DecryptGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        if app.terminal.is_running:
            app.terminal.stop_process()
        sys.exit(0)

if __name__ == "__main__":
    main()