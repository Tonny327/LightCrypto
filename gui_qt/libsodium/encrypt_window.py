"""
LightCrypto GUI - LibSodium Encrypt (Отправитель) - PyQt6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QLineEdit, QGroupBox,
                             QRadioButton, QButtonGroup, QScrollArea, QFileDialog,
                             QMessageBox, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from common.constants import *
from common.config import ConfigManager
from common.terminal import EmbeddedTerminal
from common.base_window import BaseWindow
from common.utils import (
    validate_ip, validate_port, check_tap_interface,
    get_tap_status, find_terminal_emulator
)
import subprocess


class LibSodiumEncryptGUI(BaseWindow):
    """
    GUI для LibSodium шифрования (Отправитель) - PyQt6
    """
    
    def __init__(self, config: ConfigManager, on_back):
        super().__init__("🔐 LightCrypto - LibSodium Encrypt (Отправитель)", config)
        self.on_back_callback = on_back
        self.terminal = None
        
        # Переменные
        self.ip = config.get_libsodium_encrypt_ip()
        self.port = str(config.get_libsodium_port())
        self.tap_a_ip = "10.0.0.1/24"
        self.mode = 'tap'
        self.file_path = ''
        
        # Создание виджетов
        self._create_widgets()
        self._update_tap_status()
    
    def _create_widgets(self):
        """Создание всех элементов интерфейса"""
        # Область прокрутки
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        
        # Панели
        self._create_tap_panel(scroll_widget, scroll_layout)
        self._create_network_panel(scroll_widget, scroll_layout)
        self._create_terminal_panel(scroll_widget, scroll_layout)
        self._create_utils_panel(scroll_widget, scroll_layout)
        
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        self.main_layout.addWidget(scroll_area)
    
    def _create_tap_panel(self, parent, layout):
        """Панель управления TAP-интерфейсом"""
        frame = QGroupBox(f"{EMOJI_SETTINGS} Управление TAP-интерфейсом")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(10)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        create_btn = QPushButton(f"{EMOJI_SETTINGS} Создать TAP-A")
        create_btn.setProperty("class", "success")
        create_btn.clicked.connect(self._create_tap)
        btn_layout.addWidget(create_btn)
        
        clean_btn = QPushButton(f"{EMOJI_CLEAN} Очистить TAP")
        clean_btn.setProperty("class", "warning")
        clean_btn.clicked.connect(self._clean_tap)
        btn_layout.addWidget(clean_btn)
        
        frame_layout.addLayout(btn_layout)
        
        # IP адрес TAP-A
        ip_layout = QHBoxLayout()
        ip_label = QLabel("TAP-A IP:")
        ip_label.setFixedWidth(100)
        ip_layout.addWidget(ip_label)
        
        self.tap_a_ip_entry = QLineEdit(self.tap_a_ip)
        ip_layout.addWidget(self.tap_a_ip_entry)
        
        frame_layout.addLayout(ip_layout)
        
        # Статус
        self.tap_status_label = QLabel(f"Статус: {STATUS_TAP_NOT_CREATED}")
        frame_layout.addWidget(self.tap_status_label)
        
        layout.addWidget(frame)
    
    def _create_network_panel(self, parent, layout):
        """Панель сетевых параметров"""
        frame = QGroupBox("🌐 Сетевые параметры")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(10)
        
        # Выбор режима работы
        mode_group = QGroupBox("Режим работы")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_group = QButtonGroup()
        
        tap_radio = QRadioButton("🔀 Ethernet кадры (TAP)")
        tap_radio.setChecked(True)
        self.mode_group.addButton(tap_radio, 0)
        mode_layout.addWidget(tap_radio)
        
        msg_radio = QRadioButton("💬 Текстовые сообщения (--msg)")
        msg_radio.setToolTip(TOOLTIP_MSG_MODE)
        self.mode_group.addButton(msg_radio, 1)
        mode_layout.addWidget(msg_radio)
        
        file_radio = QRadioButton(f"{EMOJI_FILE} Отправка файлов (--file)")
        file_radio.setToolTip(TOOLTIP_FILE_SELECT)
        self.mode_group.addButton(file_radio, 2)
        mode_layout.addWidget(file_radio)
        
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        
        frame_layout.addWidget(mode_group)
        
        # Панель выбора файла (скрыта по умолчанию)
        self.file_input_frame = QFrame()
        file_layout = QVBoxLayout(self.file_input_frame)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        file_label = QLabel("Файл для отправки:")
        file_layout.addWidget(file_label)
        
        file_entry_layout = QHBoxLayout()
        self.file_entry = QLineEdit()
        self.file_entry.setToolTip(TOOLTIP_FILE_SELECT)
        file_entry_layout.addWidget(self.file_entry)
        
        file_browse_btn = QPushButton(f"{EMOJI_FOLDER} Выбрать")
        file_browse_btn.setProperty("class", "info")
        file_browse_btn.clicked.connect(self._browse_file)
        file_entry_layout.addWidget(file_browse_btn)
        
        file_layout.addLayout(file_entry_layout)
        self.file_input_frame.hide()
        
        frame_layout.addWidget(self.file_input_frame)
        
        # Разделитель
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        frame_layout.addWidget(separator1)
        
        # IP-адрес
        ip_layout = QHBoxLayout()
        ip_label = QLabel("IP-адрес получателя:")
        ip_label.setFixedWidth(150)
        ip_layout.addWidget(ip_label)
        
        self.ip_entry = QLineEdit(self.ip)
        self.ip_entry.setToolTip(TOOLTIP_IP_ENCRYPT)
        ip_layout.addWidget(self.ip_entry)
        
        frame_layout.addLayout(ip_layout)
        
        # Порт
        port_layout = QHBoxLayout()
        port_label = QLabel("Порт:")
        port_label.setFixedWidth(150)
        port_layout.addWidget(port_label)
        
        self.port_entry = QLineEdit(self.port)
        self.port_entry.setToolTip(TOOLTIP_PORT)
        port_layout.addWidget(self.port_entry)
        
        frame_layout.addLayout(port_layout)
        
        # Разделитель
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        frame_layout.addWidget(separator2)
        
        # Кнопка запуска/остановки
        self.start_button = QPushButton(f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ")
        self.start_button.setProperty("class", "success")
        self.start_button.clicked.connect(self._toggle_encryption)
        frame_layout.addWidget(self.start_button)
        
        layout.addWidget(frame)
    
    def _create_terminal_panel(self, parent, layout):
        """Встроенный терминал"""
        frame = QGroupBox("📋 Терминал")
        frame_layout = QVBoxLayout(frame)
        
        self.terminal = EmbeddedTerminal(self)
        frame_layout.addWidget(self.terminal)
        
        # Увеличиваем размер терминала - устанавливаем stretch=3
        # Дополнительное увеличение на 10% через минимальную высоту в terminal.py
        layout.addWidget(frame, 3)
    
    def _create_utils_panel(self, parent, layout):
        """Панель тестовых утилит"""
        frame = QGroupBox("🧪 Генерация тестового трафика")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(10)
        
        # Первый ряд кнопок
        row1 = QHBoxLayout()
        
        self.ping_btn = QPushButton(f"{EMOJI_PING} ping")
        self.ping_btn.setProperty("class", "info")
        self.ping_btn.clicked.connect(lambda: self._run_test_util(f"ping {self._get_tap_b_ip()}"))
        row1.addWidget(self.ping_btn)
        
        self.iperf_tcp_btn = QPushButton(f"{EMOJI_IPERF} iperf TCP")
        self.iperf_tcp_btn.setProperty("class", "info")
        self.iperf_tcp_btn.clicked.connect(lambda: self._run_test_util(f"iperf -c {self._get_tap_b_ip()} -t 10"))
        row1.addWidget(self.iperf_tcp_btn)
        
        self.iperf_udp_btn = QPushButton(f"{EMOJI_IPERF} iperf UDP")
        self.iperf_udp_btn.setProperty("class", "info")
        self.iperf_udp_btn.clicked.connect(lambda: self._run_test_util(f"iperf -c {self._get_tap_b_ip()} -u -t 10 -b 100M"))
        row1.addWidget(self.iperf_udp_btn)
        
        frame_layout.addLayout(row1)
        
        # Второй ряд кнопок
        row2 = QHBoxLayout()
        
        self.hping_syn_btn = QPushButton(f"{EMOJI_HPING} hping3 SYN")
        self.hping_syn_btn.setProperty("class", "info")
        self.hping_syn_btn.clicked.connect(lambda: self._run_test_util(f"sudo hping3 {self._get_tap_b_ip()} -S -p 80 -c 10"))
        row2.addWidget(self.hping_syn_btn)
        
        self.hping_udp_btn = QPushButton(f"{EMOJI_HPING} hping3 UDP")
        self.hping_udp_btn.setProperty("class", "info")
        self.hping_udp_btn.clicked.connect(lambda: self._run_test_util(f"sudo hping3 {self._get_tap_b_ip()} -2 -p 5000 -c 10"))
        row2.addWidget(self.hping_udp_btn)
        
        frame_layout.addLayout(row2)
        
        # Сохраняем ссылки на кнопки
        self.test_buttons = [
            self.ping_btn, self.iperf_tcp_btn, self.iperf_udp_btn,
            self.hping_syn_btn, self.hping_udp_btn
        ]
        
        layout.addWidget(frame)
    
    def _update_tap_status(self):
        """Обновление статуса TAP интерфейса"""
        exists, ip = get_tap_status(TAP_NAMES['encrypt'])
        
        if exists and ip:
            self.tap_status_label.setText(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['encrypt']} ({ip})")
        elif exists:
            self.tap_status_label.setText(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['encrypt']}")
        else:
            self.tap_status_label.setText(f"Статус: {STATUS_TAP_NOT_CREATED}")
        
        # Повторная проверка через 2 секунды
        QTimer.singleShot(2000, self._update_tap_status)
    
    def _create_tap(self):
        """Создание TAP-интерфейса"""
        self.terminal.print_to_terminal(f"{EMOJI_SETTINGS} Создание {TAP_NAMES['encrypt']}...", 'info')
        
        try:
            tap_a_ip = self.tap_a_ip_entry.text().strip()
            result = subprocess.run(
                ['sudo', 'bash', SETUP_TAP_A, tap_a_ip],
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
            QMessageBox.warning(
                self,
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
        ip = self.ip_entry.text().strip()
        port_str = self.port_entry.text().strip()
        mode_id = self.mode_group.checkedId()
        mode = ['tap', 'msg', 'file'][mode_id]
        
        if not validate_ip(ip):
            QMessageBox.critical(self, "Ошибка", "Некорректный IP-адрес!")
            return
        
        try:
            port = int(port_str)
            if not validate_port(port):
                raise ValueError()
        except:
            QMessageBox.critical(self, "Ошибка", f"Некорректный порт! Допустимый диапазон: {PORT_MIN}-{PORT_MAX}")
            return
        
        # Валидация для режима файлов
        if mode == 'file':
            file_path = self.file_entry.text().strip()
            if not file_path:
                QMessageBox.critical(self, "Ошибка", "Выберите файл для отправки!")
                return
            
            if not os.path.isfile(file_path):
                QMessageBox.critical(self, "Ошибка", f"Файл не найден: {file_path}")
                return
        
        # Сохранение параметров
        self.config.set_libsodium_encrypt_ip(ip)
        self.config.set_libsodium_port(port)
        self.config.set_libsodium_msg_mode(mode == 'msg')
        self.config.save()
        
        # Формирование команды
        cmd = ['sudo', TAP_ENCRYPT]
        
        if mode == 'msg':
            cmd.append('--msg')
        elif mode == 'file':
            cmd.append('--file')
            cmd.append(self.file_entry.text())
        
        cmd.append(ip)
        cmd.append(str(port))
        
        # Запуск
        self.terminal.run_process(cmd, use_xterm=False)
        
        # Показать поле ввода если режим сообщений
        if mode == 'msg':
            self.terminal.show_input_field(True)
        
        # Обновление кнопки
        self.start_button.setText(f"{EMOJI_STOP} ОСТАНОВИТЬ ШИФРОВАНИЕ")
        self.start_button.setProperty("class", "error")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
    
    def _stop_encryption(self):
        """Остановка шифрования"""
        self.terminal.stop_process()
        self._reset_after_process_end()

    def _reset_after_process_end(self):
        """Сброс состояния интерфейса после завершения процесса"""
        # Скрыть поле ввода
        self.terminal.show_input_field(False)

        # Обновление кнопки
        self.start_button.setText(f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ")
        self.start_button.setProperty("class", "success")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
    
    def _on_mode_changed(self):
        """Обработка изменения режима работы"""
        mode_id = self.mode_group.checkedId()
        mode = ['tap', 'msg', 'file'][mode_id]
        self.mode = mode
        
        # Показать/скрыть панель выбора файла
        if mode == 'file':
            self.file_input_frame.show()
        else:
            self.file_input_frame.hide()
        
        # Блокировка кнопок тестовых утилит (только в режиме TAP)
        if hasattr(self, 'test_buttons'):
            enabled = (mode == 'tap')
            for btn in self.test_buttons:
                btn.setEnabled(enabled)
        
        # Информационные сообщения
        if hasattr(self, 'terminal') and self.terminal:
            if mode == 'msg':
                self.terminal.print_to_terminal(
                    f"{EMOJI_INFO} Режим сообщений включен. Тестовые утилиты отключены.",
                    'info'
                )
            elif mode == 'file':
                self.terminal.print_to_terminal(
                    f"{EMOJI_INFO} Режим отправки файлов включен.",
                    'info'
                )
            elif mode == 'tap':
                self.terminal.print_to_terminal(
                    f"{EMOJI_INFO} Режим Ethernet-кадров активен.",
                    'info'
                )
    
    def _browse_file(self):
        """Выбор файла для отправки"""
        initial_dir = self.config.get_last_file_dir()
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для отправки",
            initial_dir,
            "Все файлы (*.*);;Изображения (*.png *.jpg *.jpeg *.gif *.bmp);;Документы (*.pdf *.doc *.docx *.txt);;Архивы (*.zip *.rar *.7z *.tar *.gz)"
        )
        
        if filepath:
            self.file_entry.setText(filepath)
            # Сохранить директорию
            self.config.set_last_file_dir(os.path.dirname(filepath))
            self.config.save()
            
            self.terminal.print_to_terminal(
                f"{EMOJI_FILE} Выбран файл: {os.path.basename(filepath)}",
                'success'
            )
    
    def _get_tap_b_ip(self):
        """Получить IP адрес TAP-B (без маски)"""
        return "10.0.0.2"
    
    def _run_test_util(self, command: str):
        """Запуск тестовой утилиты в отдельном терминале"""
        terminal = find_terminal_emulator()
        
        if not terminal:
            QMessageBox.critical(
                self,
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
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.terminal and self.terminal.is_running:
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                "Процесс шифрования запущен. Остановить и закрыть?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.terminal.stop_process()
            else:
                event.ignore()
                return
        
        self._save_geometry()
        self.config.save()
        super().closeEvent(event)
        if self.on_back_callback:
            self.on_back_callback()
    
    def run(self):
        """Запуск главного цикла окна"""
        self.show()

    def on_terminal_process_finished(self):
        """Callback от встроенного терминала при завершении процесса"""
        self._reset_after_process_end()

