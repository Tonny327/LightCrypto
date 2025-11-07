"""
LightCrypto GUI - Панель параметров Custom Digital Codec (PyQt6)
Переиспользуемый компонент для управления параметрами кодека
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
                             QComboBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from common.constants import *
from common.config import ConfigManager
from common.utils import scan_csv_files, analyze_csv, validate_codec_params


class CodecPanel(QGroupBox):
    """
    Панель управления параметрами цифрового кодека (PyQt6)
    """
    
    def __init__(self, config: ConfigManager, terminal=None, parent=None):
        """
        Args:
            config: Менеджер конфигурации
            terminal: Объект терминала для вывода сообщений (optional)
            parent: Родительский виджет
        """
        super().__init__(f"{EMOJI_SETTINGS} Параметры цифрового кодека", parent)
        self.config = config
        self.terminal = terminal
        
        # Данные CSV
        self.csv_analysis = None
        self.csv_files = []
        
        # Создание панели
        self._create_widgets()
        self._scan_csv_files()
        
        # Загрузка последнего CSV
        last_csv = config.get_custom_csv()
        if last_csv and last_csv in self.csv_files:
            self.csv_combo.setCurrentText(last_csv)
            self._on_csv_selected()
    
    def _create_widgets(self):
        """Создание всех элементов панели"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # CSV файл
        self._create_csv_section(layout)
        
        # Параметры алгоритма
        self._create_params_section(layout)
        
        # Тестирование и отладка
        self._create_debug_section(layout)
        
        # Статус конфигурации
        self._create_status_section(layout)
    
    def _create_csv_section(self, parent_layout):
        """Секция выбора CSV"""
        csv_group = QGroupBox("Файл ключа (CSV)")
        csv_layout = QHBoxLayout(csv_group)
        
        self.csv_combo = QComboBox()
        self.csv_combo.setEditable(False)
        self.csv_combo.currentTextChanged.connect(self._on_csv_selected)
        # Отключаем изменение значения колесиком мыши
        self.csv_combo.wheelEvent = lambda event: None
        csv_layout.addWidget(self.csv_combo)
        
        browse_btn = QPushButton(f"{EMOJI_FOLDER} Обзор")
        browse_btn.setProperty("class", "info")
        browse_btn.clicked.connect(self._browse_csv)
        csv_layout.addWidget(browse_btn)
        
        parent_layout.addWidget(csv_group)
    
    def _create_params_section(self, parent_layout):
        """Секция параметров алгоритма"""
        params_group = QGroupBox("Параметры алгоритма")
        params_layout = QGridLayout(params_group)
        params_layout.setColumnStretch(1, 1)
        
        row = 0
        
        # M
        params_layout.addWidget(QLabel("M (разрядность):"), row, 0)
        self.M_spin = QSpinBox()
        self.M_spin.setRange(CODEC_M_MIN, CODEC_M_MAX)
        self.M_spin.setValue(self.config.get_custom_M())
        self.M_spin.setToolTip(TOOLTIP_M)
        # Отключаем изменение значения колесиком мыши
        self.M_spin.wheelEvent = lambda event: None
        params_layout.addWidget(self.M_spin, row, 1)
        row += 1
        
        # Q
        params_layout.addWidget(QLabel("Q (информационные биты):"), row, 0)
        self.Q_spin = QSpinBox()
        self.Q_spin.setRange(CODEC_Q_MIN, CODEC_Q_MAX)
        self.Q_spin.setValue(self.config.get_custom_Q())
        self.Q_spin.setToolTip(TOOLTIP_Q)
        # Отключаем изменение значения колесиком мыши
        self.Q_spin.wheelEvent = lambda event: None
        params_layout.addWidget(self.Q_spin, row, 1)
        row += 1
        
        # Авто Q из CSV
        self.auto_Q_check = QCheckBox("Авто Q из CSV")
        self.auto_Q_check.setChecked(self.config.get_custom_auto_q())
        self.auto_Q_check.toggled.connect(self._on_auto_q_changed)
        params_layout.addWidget(self.auto_Q_check, row, 0, 1, 2)
        row += 1
        
        # Тип функции
        params_layout.addWidget(QLabel("Тип функции:"), row, 0)
        self.funType_combo = QComboBox()
        for fun_type in CODEC_FUN_TYPES:
            self.funType_combo.addItem(fun_type)
        self.funType_combo.setCurrentIndex(self.config.get_custom_funType() - 1)
        self.funType_combo.currentIndexChanged.connect(self._on_funtype_selected)
        # Отключаем изменение значения колесиком мыши
        self.funType_combo.wheelEvent = lambda event: None
        params_layout.addWidget(self.funType_combo, row, 1)
        row += 1
        
        # h1
        params_layout.addWidget(QLabel("h1 (начальное состояние 1):"), row, 0)
        self.h1_spin = QSpinBox()
        self.h1_spin.setRange(-1000, 1000)
        self.h1_spin.setValue(self.config.get_custom_h1())
        self.h1_spin.setToolTip(TOOLTIP_H1_H2)
        # Отключаем изменение значения колесиком мыши
        self.h1_spin.wheelEvent = lambda event: None
        params_layout.addWidget(self.h1_spin, row, 1)
        row += 1
        
        # h2
        params_layout.addWidget(QLabel("h2 (начальное состояние 2):"), row, 0)
        self.h2_spin = QSpinBox()
        self.h2_spin.setRange(-1000, 1000)
        self.h2_spin.setValue(self.config.get_custom_h2())
        self.h2_spin.setToolTip(TOOLTIP_H1_H2)
        # Отключаем изменение значения колесиком мыши
        self.h2_spin.wheelEvent = lambda event: None
        params_layout.addWidget(self.h2_spin, row, 1)
        
        parent_layout.addWidget(params_group)
    
    def _create_debug_section(self, parent_layout):
        """Секция тестирования и отладки"""
        debug_group = QGroupBox("Тестирование и отладка")
        debug_layout = QVBoxLayout(debug_group)
        
        # Режим отладки
        self.debug_check = QCheckBox("Режим отладки")
        self.debug_check.setChecked(self.config.get_custom_debug())
        self.debug_check.setToolTip("Показывает процесс проверки гипотез об ошибках")
        debug_layout.addWidget(self.debug_check)
        
        # Искусственное внесение ошибок
        self.inject_errors_check = QCheckBox("Искусственное внесение ошибок")
        self.inject_errors_check.setChecked(self.config.get_custom_inject_errors())
        self.inject_errors_check.toggled.connect(self._on_inject_errors_toggled)
        debug_layout.addWidget(self.inject_errors_check)
        
        # Вероятность ошибки
        error_rate_layout = QHBoxLayout()
        error_rate_layout.addWidget(QLabel("Вероятность ошибки (%):"))
        self.error_rate_spin = QDoubleSpinBox()
        self.error_rate_spin.setRange(0.0, 100.0)
        self.error_rate_spin.setValue(self.config.get_custom_error_rate())
        self.error_rate_spin.setDecimals(2)
        self.error_rate_spin.setSingleStep(0.1)
        # Отключаем изменение значения колесиком мыши
        self.error_rate_spin.wheelEvent = lambda event: None
        if not self.inject_errors_check.isChecked():
            self.error_rate_spin.setEnabled(False)
        error_rate_layout.addWidget(self.error_rate_spin)
        debug_layout.addLayout(error_rate_layout)
        
        # Информация
        debug_info = QLabel(
            "💡 Режим отладки показывает процесс проверки гипотез об ошибках.\n"
            "Внесение ошибок позволяет протестировать работу алгоритма исправления."
        )
        debug_info.setWordWrap(True)
        debug_info.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY_DARK};")
        debug_layout.addWidget(debug_info)
        
        parent_layout.addWidget(debug_group)
    
    def _create_status_section(self, parent_layout):
        """Секция статуса конфигурации"""
        status_group = QGroupBox("Статус конфигурации")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("⚪ Не проверено")
        status_layout.addWidget(self.status_label)
        
        # Кнопка проверки
        validate_btn = QPushButton(f"{EMOJI_REFRESH} Проверить параметры")
        validate_btn.clicked.connect(self._validate_params)
        status_layout.addWidget(validate_btn)
        
        parent_layout.addWidget(status_group)
    
    def _scan_csv_files(self):
        """Сканирование CSV файлов"""
        self.csv_files = scan_csv_files()
        self.csv_combo.clear()
        self.csv_combo.addItems(self.csv_files)
    
    def _browse_csv(self):
        """Выбор CSV файла через диалог"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите CSV файл ключа",
            CIPHER_KEYS_DIR,
            "CSV файлы (*.csv);;Все файлы (*.*)"
        )
        
        if filepath:
            filename = os.path.basename(filepath)
            if filename not in self.csv_files:
                self.csv_files.append(filename)
                self.csv_combo.addItem(filename)
            self.csv_combo.setCurrentText(filename)
            self._on_csv_selected()
    
    def _on_csv_selected(self):
        """Обработка выбора CSV файла"""
        csv_name = self.csv_combo.currentText()
        if not csv_name:
            return
        
        csv_path = os.path.join(CIPHER_KEYS_DIR, csv_name)
        self.csv_analysis = analyze_csv(csv_path)
        
        if self.csv_analysis['success']:
            # Автоматически установить Q если включен авто-режим
            if self.auto_Q_check.isChecked() and self.csv_analysis['Q'] > 0:
                self.Q_spin.setValue(self.csv_analysis['Q'])
            
            # Обновить список допустимых типов функций
            self._update_funtype_combo()
            
            if self.terminal:
                self.terminal.print_to_terminal(
                    f"{EMOJI_SUCCESS} CSV загружен: {csv_name} (Q={self.csv_analysis['Q']}, строк={self.csv_analysis['rows']})",
                    'success'
                )
        else:
            if self.terminal:
                self.terminal.print_to_terminal(
                    f"{EMOJI_ERROR} Ошибка анализа CSV: {self.csv_analysis['error']}",
                    'error'
                )
    
    def _update_funtype_combo(self):
        """Обновление списка допустимых типов функций"""
        if not self.csv_analysis or not self.csv_analysis['success']:
            return
        
        valid_types = self.csv_analysis.get('valid_fun_types', [])
        current_index = self.funType_combo.currentIndex() + 1
        
        # Если текущий тип недопустим, выбрать первый допустимый
        if valid_types and current_index not in valid_types:
            if valid_types:
                self.funType_combo.setCurrentIndex(valid_types[0] - 1)
    
    def _on_auto_q_changed(self):
        """Обработка изменения чекбокса авто-Q"""
        if self.auto_Q_check.isChecked() and self.csv_analysis and self.csv_analysis['success']:
            self.Q_spin.setValue(self.csv_analysis['Q'])
            self.Q_spin.setEnabled(False)
        else:
            self.Q_spin.setEnabled(True)
    
    def _on_funtype_selected(self):
        """Обработка выбора типа функции"""
        # Можно добавить дополнительную логику
        pass
    
    def _on_inject_errors_toggled(self):
        """Обработчик изменения состояния чекбокса внесения ошибок"""
        self.error_rate_spin.setEnabled(self.inject_errors_check.isChecked())
    
    def _validate_params(self):
        """Валидация параметров"""
        csv_name = self.csv_combo.currentText()
        if not csv_name:
            self.status_label.setText("🔴 Ошибка: Выберите CSV файл")
            return False
        
        csv_path = os.path.join(CIPHER_KEYS_DIR, csv_name)
        if not os.path.isfile(csv_path):
            self.status_label.setText("🔴 Ошибка: CSV файл не найден")
            return False
        
        M = self.M_spin.value()
        Q = self.Q_spin.value()
        
        # Анализ CSV если еще не сделан
        if not self.csv_analysis or not self.csv_analysis['success']:
            self.csv_analysis = analyze_csv(csv_path)
        
        csv_rows = self.csv_analysis.get('rows', 0) if self.csv_analysis else 0
        
        valid, errors = validate_codec_params(M, Q, csv_rows)
        
        if valid:
            self.status_label.setText("🟢 Параметры корректны")
            if self.terminal:
                self.terminal.print_to_terminal(f"{EMOJI_SUCCESS} Параметры валидны", 'success')
            return True
        else:
            error_text = "; ".join(errors)
            self.status_label.setText(f"🔴 Ошибки: {error_text}")
            if self.terminal:
                self.terminal.print_to_terminal(f"{EMOJI_ERROR} Ошибки валидации: {error_text}", 'error')
            return False
    
    def get_params(self):
        """Получение текущих параметров"""
        csv_name = self.csv_combo.currentText()
        return {
            'csv_file': csv_name,
            'csv_path': os.path.join(CIPHER_KEYS_DIR, csv_name) if csv_name else '',
            'M': self.M_spin.value(),
            'Q': self.Q_spin.value(),
            'funType': self.funType_combo.currentIndex() + 1,
            'h1': self.h1_spin.value(),
            'h2': self.h2_spin.value(),
            'debug': self.debug_check.isChecked(),
            'injectErrors': self.inject_errors_check.isChecked(),
            'errorRate': self.error_rate_spin.value() / 100.0  # Конвертируем проценты в долю
        }
    
    def save_to_config(self):
        """Сохранение параметров в конфигурацию"""
        self.config.set_custom_csv(self.csv_combo.currentText())
        self.config.set_custom_M(self.M_spin.value())
        self.config.set_custom_Q(self.Q_spin.value())
        self.config.set_custom_funType(self.funType_combo.currentIndex() + 1)
        self.config.set_custom_h1(self.h1_spin.value())
        self.config.set_custom_h2(self.h2_spin.value())
        self.config.set_custom_auto_q(self.auto_Q_check.isChecked())
        self.config.set_custom_debug(self.debug_check.isChecked())
        self.config.set_custom_inject_errors(self.inject_errors_check.isChecked())
        self.config.set_custom_error_rate(self.error_rate_spin.value())
    
    def is_valid(self):
        """Проверка валидности текущих параметров"""
        return self._validate_params()

