"""
LightCrypto GUI - LibSodium Decrypt (Получатель) - PyQt6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QGroupBox,
                             QRadioButton, QButtonGroup, QScrollArea, QFileDialog,
                             QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from common.constants import *
from common.config import ConfigManager
from common.terminal import EmbeddedTerminal
from common.base_window import BaseWindow
from common.utils import (
    validate_port, check_tap_interface,
    get_tap_status, find_terminal_emulator
)
import subprocess


class LibSodiumDecryptGUI(BaseWindow):
    """
    GUI для LibSodium расшифровки (Получатель) - PyQt6
    """
    
    def __init__(self, config: ConfigManager, on_back):
        super().__init__("🔐 LightCrypto - LibSodium Decrypt (Получатель)", config)
        self.on_back_callback = on_back
        self.terminal = None
        
        # Переменные
        self.ip = DEFAULT_DECRYPT_IP
        self.port = str(config.get_libsodium_port())
        self.tap_b_ip = "10.0.0.2/24"
        self.mode = 'tap'
        self.output_path = ''
        
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
        
        create_btn = QPushButton(f"{EMOJI_SETTINGS} Создать TAP-B")
        create_btn.setProperty("class", "success")
        create_btn.clicked.connect(self._create_tap)
        btn_layout.addWidget(create_btn)
        
        clean_btn = QPushButton(f"{EMOJI_CLEAN} Очистить TAP")
        clean_btn.setProperty("class", "warning")
        clean_btn.clicked.connect(self._clean_tap)
        btn_layout.addWidget(clean_btn)
        
        frame_layout.addLayout(btn_layout)
        
        # IP адрес TAP-B
        ip_layout = QHBoxLayout()
        ip_label = QLabel("TAP-B IP:")
        ip_label.setFixedWidth(100)
        ip_layout.addWidget(ip_label)
        
        self.tap_b_ip_entry = QLineEdit(self.tap_b_ip)
        ip_layout.addWidget(self.tap_b_ip_entry)
        
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
        
        file_radio = QRadioButton(f"{EMOJI_FILE} Прием файлов (--file)")
        file_radio.setToolTip(TOOLTIP_FILE_MODE)
        self.mode_group.addButton(file_radio, 2)
        mode_layout.addWidget(file_radio)
        
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        
        frame_layout.addWidget(mode_group)
        
        # Панель выбора пути сохранения (скрыта по умолчанию)
        self.file_output_frame = QFrame()
        file_layout = QVBoxLayout(self.file_output_frame)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        output_label = QLabel("Путь/имя файла для сохранения (необязательно):")
        file_layout.addWidget(output_label)
        
        output_entry_layout = QHBoxLayout()
        self.output_entry = QLineEdit()
        self.output_entry.setPlaceholderText("Например: /home/user/output/received_file.png")
        self.output_entry.setToolTip(TOOLTIP_FILE_OUTPUT)
        output_entry_layout.addWidget(self.output_entry)
        
        output_browse_btn = QPushButton(f"{EMOJI_FOLDER} Выбрать")
        output_browse_btn.setProperty("class", "info")
        output_browse_btn.clicked.connect(self._browse_output)
        output_entry_layout.addWidget(output_browse_btn)
        
        file_layout.addLayout(output_entry_layout)
        
        output_hint = QLabel("(Пусто = сохранить с оригинальным именем в текущей папке)")
        output_hint.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY_DARK}; font-size: 8pt;")
        file_layout.addWidget(output_hint)
        
        self.file_output_frame.hide()
        
        frame_layout.addWidget(self.file_output_frame)
        
        # Разделитель
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        frame_layout.addWidget(separator1)
        
        # IP-адрес
        ip_layout = QHBoxLayout()
        ip_label = QLabel("IP прослушивания:")
        ip_label.setFixedWidth(150)
        ip_layout.addWidget(ip_label)
        
        self.ip_entry = QLineEdit(self.ip)
        self.ip_entry.setToolTip(TOOLTIP_IP_DECRYPT)
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
        self.start_button = QPushButton(f"{EMOJI_PLAY} ЗАПУСТИТЬ РАСШИФРОВКУ")
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
        """Панель сервисов для тестирования"""
        frame = QGroupBox("🛰️ Сервисы для тестирования")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(10)
        
        # Кнопки сервисов
        row1 = QHBoxLayout()
        
        iperf_tcp_srv_btn = QPushButton(f"{EMOJI_SERVER} iperf TCP сервер")
        iperf_tcp_srv_btn.setProperty("class", "info")
        iperf_tcp_srv_btn.clicked.connect(lambda: self._run_service(f"iperf -s -B {self._get_tap_b_ip()}"))
        row1.addWidget(iperf_tcp_srv_btn)
        
        iperf_udp_srv_btn = QPushButton(f"{EMOJI_SERVER} iperf UDP сервер")
        iperf_udp_srv_btn.setProperty("class", "info")
        iperf_udp_srv_btn.clicked.connect(lambda: self._run_service(f"iperf -s -u -B {self._get_tap_b_ip()}"))
        row1.addWidget(iperf_udp_srv_btn)
        
        tcpdump_btn = QPushButton(f"{EMOJI_TCPDUMP} tcpdump tap1")
        tcpdump_btn.setProperty("class", "info")
        tcpdump_btn.clicked.connect(lambda: self._run_service("sudo tcpdump -i tap1 -v"))
        row1.addWidget(tcpdump_btn)
        
        frame_layout.addLayout(row1)
        
        layout.addWidget(frame)
    
    def _update_tap_status(self):
        """Обновление статуса TAP интерфейса"""
        exists, ip = get_tap_status(TAP_NAMES['decrypt'])
        
        if exists and ip:
            self.tap_status_label.setText(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['decrypt']} ({ip})")
        elif exists:
            self.tap_status_label.setText(f"{STATUS_TAP_ACTIVE} {TAP_NAMES['decrypt']}")
        else:
            self.tap_status_label.setText(f"Статус: {STATUS_TAP_NOT_CREATED}")
        
        # Повторная проверка через 2 секунды
        QTimer.singleShot(2000, self._update_tap_status)
    
    def _create_tap(self):
        """Создание TAP-интерфейса"""
        self.terminal.print_to_terminal(f"{EMOJI_SETTINGS} Создание {TAP_NAMES['decrypt']}...", 'info')
        
        try:
            tap_b_ip = self.tap_b_ip_entry.text().strip()
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
            QMessageBox.warning(
                self,
                "Внимание",
                "Сначала остановите процесс расшифровки!"
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
        """Запуск/остановка расшифровки"""
        if self.terminal.is_running:
            self._stop_encryption()
        else:
            self._start_encryption()
    
    def _start_encryption(self):
        """Запуск расшифровки"""
        # Валидация
        port_str = self.port_entry.text().strip()
        mode_id = self.mode_group.checkedId()
        mode = ['tap', 'msg', 'file'][mode_id]
        
        try:
            port = int(port_str)
            if not validate_port(port):
                raise ValueError()
        except:
            QMessageBox.critical(self, "Ошибка", f"Некорректный порт! Допустимый диапазон: {PORT_MIN}-{PORT_MAX}")
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
            output_path = self.output_entry.text().strip()
            if output_path:
                cmd.append('--output')
                cmd.append(output_path)
        
        cmd.append(str(port))
        
        # Запуск
        self.terminal.run_process(cmd, use_xterm=False)
        
        # Обновление кнопки
        self.start_button.setText(f"{EMOJI_STOP} ОСТАНОВИТЬ РАСШИФРОВКУ")
        self.start_button.setProperty("class", "error")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
    
    def _stop_encryption(self):
        """Остановка расшифровки"""
        self.terminal.stop_process()
        self._reset_after_process_end()

    def _reset_after_process_end(self):
        """Сброс состояния интерфейса после завершения процесса"""
        self.start_button.setText(f"{EMOJI_PLAY} ЗАПУСТИТЬ РАСШИФРОВКУ")
        self.start_button.setProperty("class", "success")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
    
    def _on_mode_changed(self):
        """Обработка изменения режима работы"""
        mode_id = self.mode_group.checkedId()
        mode = ['tap', 'msg', 'file'][mode_id]
        self.mode = mode
        
        # Показать/скрыть панель выбора пути сохранения
        if mode == 'file':
            self.file_output_frame.show()
        else:
            self.file_output_frame.hide()
        
        # Информационные сообщения
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
        """Выбор пути и имени файла для сохранения"""
        initial_dir = self.config.get_last_output_dir()
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите имя и формат сохраняемого файла",
            initial_dir,
            "Все файлы (*.*);;Изображения (*.png *.jpg *.jpeg *.gif *.bmp);;Документы (*.pdf *.doc *.docx *.txt);;Архивы (*.zip *.rar *.7z *.tar *.gz)"
        )

        if filepath:
            self.output_entry.setText(filepath)
            # Сохранить директорию
            self.config.set_last_output_dir(os.path.dirname(filepath))
            self.config.save()

            self.terminal.print_to_terminal(
                f"{EMOJI_FOLDER} Файл будет сохранен как: {filepath}",
                'success'
            )
    
    def _get_tap_b_ip(self):
        """Получить IP адрес TAP-B (без маски)"""
        return "10.0.0.2"
    
    def _run_service(self, command: str):
        """Запуск сервиса в отдельном терминале"""
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
            self.terminal.print_to_terminal(f"{EMOJI_INFO} Запущен сервис: {command}", 'info')
        except Exception as e:
            self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибка запуска: {e}", 'error')
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.terminal and self.terminal.is_running:
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                "Процесс расшифровки запущен. Остановить и закрыть?",
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

