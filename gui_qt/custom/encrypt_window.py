"""
LightCrypto GUI - Custom Codec Encrypt (Отправитель) - PyQt6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QMessageBox

from common.constants import *
from common.config import ConfigManager
from libsodium.encrypt_window import LibSodiumEncryptGUI
from custom.codec_panel import CodecPanel
from common.utils import validate_ip, validate_port


class CustomCodecEncryptGUI(LibSodiumEncryptGUI):
    """
    GUI для Custom Digital Codec шифрования (Отправитель) - PyQt6
    Наследует LibSodium GUI и добавляет панель параметров кодека
    """
    
    def __init__(self, config: ConfigManager, on_back):
        # Изменяем заголовок окна
        self._window_title = "🔐 LightCrypto - Custom Codec Encrypt (Отправитель)"
        self.codec_panel = None
        super().__init__(config, on_back)
        self.setWindowTitle(self._window_title)
    
    def _create_widgets(self):
        """Создание всех элементов интерфейса"""
        # Сначала вызываем родительский метод для создания всех виджетов
        super()._create_widgets()
        
        # Теперь получаем ScrollArea и добавляем панель кодека
        scroll_area = self.main_layout.itemAt(0).widget()
        if scroll_area:
            scroll_widget = scroll_area.widget()
            scroll_layout = scroll_widget.layout()
            
            # ВАЖНО: Добавляем панель параметров кодека в начало
            # terminal уже создан родительским классом в _create_terminal_panel()
            self.codec_panel = CodecPanel(self.config, self.terminal, scroll_widget)
            scroll_layout.insertWidget(0, self.codec_panel)
    
    def _start_encryption(self):
        """Запуск шифрования с параметрами кодека"""
        # Валидация параметров кодека
        if not self.codec_panel.is_valid():
            QMessageBox.critical(
                self,
                "Ошибка",
                "Некорректные параметры кодека!\n"
                "Проверьте выбор CSV и значения M, Q."
            )
            return
        
        # Валидация сети
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
        self.config.set_custom_encrypt_ip(ip)
        self.config.set_custom_port(port)
        self.config.set_custom_msg_mode(mode == 'msg')
        self.codec_panel.save_to_config()
        self.config.save()
        
        # Получение параметров кодека
        codec_params = self.codec_panel.get_params()
        
        # Формирование команды
        cmd = ['sudo', TAP_ENCRYPT]
        
        # Параметры кодека
        cmd.extend(['--codec', codec_params['csv_path']])
        cmd.extend(['--M', str(codec_params['M'])])
        cmd.extend(['--Q', str(codec_params['Q'])])
        cmd.extend(['--fun', str(codec_params['funType'])])
        cmd.extend(['--h1', str(codec_params['h1'])])
        cmd.extend(['--h2', str(codec_params['h2'])])
        
        # Параметры отладки
        if codec_params['debug']:
            cmd.append('--debug')
        
        if codec_params['injectErrors']:
            cmd.append('--inject-errors')
            cmd.append('--error-rate')
            cmd.append(str(codec_params['errorRate']))
        
        # Режим работы
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

