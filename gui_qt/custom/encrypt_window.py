"""
LightCrypto GUI - Custom Codec Encrypt (Отправитель) - PyQt6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QMessageBox, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QFrame, QRadioButton, QCheckBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

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
    
    def _create_mode_switch(self, parent, layout):
        """Создает переключатель между сетевым и локальным режимом"""
        switch_frame = QFrame()
        switch_layout = QHBoxLayout(switch_frame)
        switch_layout.setContentsMargins(10, 10, 10, 10)
        
        switch_label = QLabel("Режим работы:")
        switch_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        switch_layout.addWidget(switch_label)
        
        self.mode_switch = QCheckBox("Локальное кодирование файла")
        self.mode_switch.setToolTip("Переключить между сетевым и локальным режимом")
        self.mode_switch.stateChanged.connect(lambda: self._on_mode_switch_changed())
        switch_layout.addWidget(self.mode_switch)
        
        switch_layout.addStretch()
        
        layout.insertWidget(0, switch_frame)
    
    def _create_local_file_panel(self, parent, layout):
        """Панель для локального кодирования файлов"""
        self.local_file_frame = QGroupBox(f"{EMOJI_FILE} Локальное кодирование файла")
        local_layout = QVBoxLayout(self.local_file_frame)
        
        # Выбор входного файла
        input_layout = QHBoxLayout()
        input_label = QLabel("Входной файл:")
        input_label.setFixedWidth(120)
        input_layout.addWidget(input_label)
        
        self.local_input_entry = QLineEdit()
        input_layout.addWidget(self.local_input_entry)
        
        self.local_input_browse_btn = QPushButton("Обзор...")
        self.local_input_browse_btn.clicked.connect(self._browse_input_file)
        input_layout.addWidget(self.local_input_browse_btn)
        
        local_layout.addLayout(input_layout)
        
        # Выбор выходного контейнера
        output_layout = QHBoxLayout()
        output_label = QLabel("Выходной контейнер:")
        output_label.setFixedWidth(120)
        output_layout.addWidget(output_label)
        
        self.local_output_entry = QLineEdit()
        output_layout.addWidget(self.local_output_entry)
        
        self.local_output_browse_btn = QPushButton("Обзор...")
        self.local_output_browse_btn.clicked.connect(self._browse_output_container)
        output_layout.addWidget(self.local_output_browse_btn)
        
        local_layout.addLayout(output_layout)
        
        layout.addWidget(self.local_file_frame)
        self.local_file_frame.hide()
    
    def _create_local_start_button(self, parent, layout):
        """Создает кнопку запуска для локального режима"""
        self.local_start_button_frame = QFrame()
        button_layout = QHBoxLayout(self.local_start_button_frame)
        button_layout.setContentsMargins(10, 10, 10, 10)
        
        self.local_start_button = QPushButton(f"{EMOJI_PLAY} ЗАПУСТИТЬ КОДИРОВАНИЕ")
        self.local_start_button.setProperty("class", "success")
        self.local_start_button.clicked.connect(self._start_encryption)
        button_layout.addWidget(self.local_start_button)
        
        layout.addWidget(self.local_start_button_frame)
        self.local_start_button_frame.hide()
    
    def _browse_input_file(self):
        """Выбор входного файла для локального кодирования"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для кодирования",
            "",
            "Все файлы (*.*)"
        )
        if filename:
            self.local_input_entry.setText(filename)
            self.file_entry.setText(filename)  # Синхронизация с основным полем
            
            # Автоматически генерируем имя контейнера на основе входного файла
            import os
            base_name = os.path.splitext(filename)[0]  # Имя файла без расширения
            container_path = base_name + ".bin"
            self.local_output_entry.setText(container_path)
            self.local_output_path = container_path
    
    def _browse_output_container(self):
        """Выбор пути сохранения контейнера"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить контейнер как",
            "",
            "LightCrypto Container (*.bin);;Все файлы (*.*)"
        )
        if filename:
            self.local_output_entry.setText(filename)
            self.local_output_path = filename
    
    def _on_mode_switch_changed(self):
        """Обработка переключения между сетевым и локальным режимом"""
        is_local_mode = self.mode_switch.isChecked()
        
        scroll_area = self.main_layout.itemAt(0).widget()
        if not scroll_area:
            return
            
        scroll_widget = scroll_area.widget()
        
        if is_local_mode:
            # Локальный режим - скрываем все сетевые панели
            for child in scroll_widget.findChildren(QGroupBox):
                text = child.title()
                if "TAP" in text or "🌐" in text or "Сетевые параметры" in text:
                    child.hide()
            
            # Скрываем кнопку запуска из сетевой панели
            if hasattr(self, 'start_button'):
                self.start_button.setParent(None)
                # Находим родительскую панель и скрываем её кнопку
                for child in scroll_widget.findChildren(QGroupBox):
                    if "Сетевые параметры" in child.title() or "🌐" in child.title():
                        for btn in child.findChildren(QPushButton):
                            if EMOJI_PLAY in btn.text():
                                btn.hide()
            
            # Показываем панель локального кодирования и кнопку запуска
            self.local_file_frame.show()
            if hasattr(self, 'local_start_button_frame'):
                self.local_start_button_frame.show()
        else:
            # Сетевой режим - показываем сетевые панели
            for child in scroll_widget.findChildren(QGroupBox):
                text = child.title()
                if "TAP" in text or "🌐" in text or "Сетевые параметры" in text:
                    child.show()
                    # Показываем все дочерние элементы
                    for subchild in child.findChildren(QGroupBox):
                        subchild.show()
                    for subchild in child.findChildren(QFrame):
                        subchild.show()
                    for subchild in child.findChildren(QLineEdit):
                        subchild.show()
                    for subchild in child.findChildren(QLabel):
                        subchild.show()
            
            # Скрываем панель локального кодирования и кнопку запуска
            self.local_file_frame.hide()
            if hasattr(self, 'local_start_button_frame'):
                self.local_start_button_frame.hide()
            
            # Показываем кнопку запуска в сетевой панели
            for child in scroll_widget.findChildren(QGroupBox):
                if "Сетевые параметры" in child.title() or "🌐" in child.title():
                    for btn in child.findChildren(QPushButton):
                        if EMOJI_PLAY in btn.text():
                            btn.show()
            
            # Вызываем родительский метод для обработки сетевых режимов
            super()._on_mode_changed()
    
    def _on_mode_changed(self):
        """Обработка изменения режима работы (только для сетевых режимов)"""
        # Этот метод вызывается только когда переключатель в сетевом режиме
        if hasattr(self, 'mode_switch') and self.mode_switch.isChecked():
            return  # Игнорируем, если включен локальный режим
        
        super()._on_mode_changed()
    
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
            
            # Создаем переключатель режимов (сетевой/локальный)
            self._create_mode_switch(scroll_widget, scroll_layout)
            
            # Находим позицию терминала и вставляем локальные элементы перед ним
            terminal_index = -1
            for i in range(scroll_layout.count()):
                item = scroll_layout.itemAt(i)
                if item:
                    widget = item.widget()
                    if widget and isinstance(widget, QGroupBox) and "Терминал" in widget.title():
                        terminal_index = i
                        break
            
            # Создаем панель для локального кодирования
            self._create_local_file_panel(scroll_widget, scroll_layout)
            
            # Создаем отдельную кнопку запуска для локального режима
            self._create_local_start_button(scroll_widget, scroll_layout)
            
            # Перемещаем локальные элементы перед терминалом, если он найден
            if terminal_index >= 0:
                # Удаляем из текущих позиций
                scroll_layout.removeWidget(self.local_file_frame)
                scroll_layout.removeWidget(self.local_start_button_frame)
                # Вставляем перед терминалом
                scroll_layout.insertWidget(terminal_index, self.local_file_frame)
                scroll_layout.insertWidget(terminal_index + 1, self.local_start_button_frame)
            
            # Инициализация видимости панелей
            self.local_file_frame.hide()  # Скрываем по умолчанию (сетевой режим)
            self.local_start_button_frame.hide()  # Скрываем по умолчанию
        
        # Переменные для локального режима
        self.local_output_path = ''
    
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
        
        # Проверяем переключатель режимов
        if hasattr(self, 'mode_switch') and self.mode_switch.isChecked():
            # Локальный режим
            mode = 'local_file'
            input_path = self.local_input_entry.text().strip()
            output_path = self.local_output_entry.text().strip()
            
            if not input_path:
                QMessageBox.critical(self, "Ошибка", "Выберите входной файл!")
                return
            
            if not os.path.isfile(input_path):
                QMessageBox.critical(self, "Ошибка", f"Файл не найден: {input_path}")
                return
            
            if not output_path:
                QMessageBox.critical(self, "Ошибка", "Укажите путь для сохранения контейнера!")
                return
            
            # Получение параметров кодека
            codec_params = self.codec_panel.get_params()
            
            if not codec_params['csv_path']:
                QMessageBox.critical(self, "Ошибка", "CSV файл не выбран!")
                return
            
            # Сохранение параметров
            self.codec_panel.save_to_config()
            self.config.save()
            
            # Формирование команды для локального кодирования
            cmd = [
                FILE_ENCODE,
                input_path,
                output_path,
                '--codec', codec_params['csv_path'],
                '--M', str(codec_params['M']),
                '--Q', str(codec_params['Q']),
                '--fun', str(codec_params['funType']),
                '--h1', str(codec_params['h1']),
                '--h2', str(codec_params['h2'])
            ]
            
            # Запуск
            self.terminal.run_process(cmd, use_xterm=False)
            
            # Обновление кнопки
            if hasattr(self, 'local_start_button'):
                self.local_start_button.setText(f"{EMOJI_STOP} ОСТАНОВИТЬ КОДИРОВАНИЕ")
                self.local_start_button.setProperty("class", "error")
                self.local_start_button.style().unpolish(self.local_start_button)
                self.local_start_button.style().polish(self.local_start_button)
            return
        
        # Обработка сетевых режимов (если переключатель не включен)
        mode_id = self.mode_group.checkedId()
        mode = ['tap', 'msg', 'file'][mode_id] if mode_id < 3 else 'tap'
        
        # Валидация сети
        ip = self.ip_entry.text().strip()
        port_str = self.port_entry.text().strip()
        
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
        
        # Обновление кнопки (сетевой режим)
        if hasattr(self, 'start_button'):
            self.start_button.setText(f"{EMOJI_STOP} ОСТАНОВИТЬ ШИФРОВАНИЕ")
            self.start_button.setProperty("class", "error")
            self.start_button.style().unpolish(self.start_button)
            self.start_button.style().polish(self.start_button)
    
    def on_terminal_process_finished(self):
        """Обработка завершения процесса - возврат кнопки в исходное состояние"""
        # Проверяем, какой режим активен
        if hasattr(self, 'mode_switch') and self.mode_switch.isChecked():
            # Локальный режим - возвращаем локальную кнопку
            if hasattr(self, 'local_start_button'):
                self.local_start_button.setText(f"{EMOJI_PLAY} ЗАПУСТИТЬ КОДИРОВАНИЕ")
                self.local_start_button.setProperty("class", "success")
                self.local_start_button.style().unpolish(self.local_start_button)
                self.local_start_button.style().polish(self.local_start_button)
        else:
            # Сетевой режим - возвращаем сетевую кнопку
            if hasattr(self, 'start_button'):
                self.start_button.setText(f"{EMOJI_PLAY} ЗАПУСТИТЬ ШИФРОВАНИЕ")
                self.start_button.setProperty("class", "success")
                self.start_button.style().unpolish(self.start_button)
                self.start_button.style().polish(self.start_button)

