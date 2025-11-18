"""
LightCrypto GUI - Менеджер конфигурации
Автоматическое сохранение и загрузка настроек
"""

import json
import os
from typing import Any, Dict
from .constants import *


class ConfigManager:
    """
    Менеджер конфигурации приложения
    Автосохранение настроек при выходе
    """
    
    def __init__(self):
        self.config_dir = os.path.expanduser('~/.config/lightcrypto')
        self.config_file = os.path.join(self.config_dir, 'gui_config.json')
        self.config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """Загрузка конфигурации из файла"""
        if os.path.isfile(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                print(f"✅ Конфигурация загружена: {self.config_file}")
            except Exception as e:
                print(f"⚠️  Ошибка загрузки конфигурации: {e}")
                self.config = {}
        else:
            print("ℹ️  Конфигурация не найдена, используются значения по умолчанию")
            self.config = {}
    
    def save(self):
        """Сохранение конфигурации в файл"""
        try:
            # Создаем директорию если не существует
            os.makedirs(self.config_dir, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            print(f"✅ Конфигурация сохранена: {self.config_file}")
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение из конфигурации
        
        Args:
            key: Ключ параметра
            default: Значение по умолчанию
        
        Returns:
            Значение параметра или default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        Установить значение в конфигурации
        
        Args:
            key: Ключ параметра
            value: Значение параметра
        """
        self.config[key] = value
    
    def get_window_geometry(self, window_name: str) -> Dict[str, int]:
        """
        Получить сохраненную геометрию окна
        
        Args:
            window_name: Имя окна
        
        Returns:
            Словарь с ключами: width, height, x, y
        """
        key = f"window_{window_name}_geometry"
        return self.get(key, {})
    
    def set_window_geometry(self, window_name: str, width: int, height: int, x: int, y: int):
        """
        Сохранить геометрию окна
        
        Args:
            window_name: Имя окна
            width, height: Размеры окна
            x, y: Позиция окна
        """
        key = f"window_{window_name}_geometry"
        self.set(key, {
            'width': width,
            'height': height,
            'x': x,
            'y': y
        })
    
    # === Специфичные методы для LibSodium ===
    
    def get_libsodium_encrypt_ip(self) -> str:
        """Получить последний использованный IP для LibSodium Encrypt"""
        return self.get('libsodium_encrypt_ip', '')
    
    def set_libsodium_encrypt_ip(self, ip: str):
        """Сохранить IP для LibSodium Encrypt"""
        self.set('libsodium_encrypt_ip', ip)
    
    def get_libsodium_port(self) -> int:
        """Получить последний использованный порт для LibSodium"""
        return self.get('libsodium_port', DEFAULT_PORT)
    
    def set_libsodium_port(self, port: int):
        """Сохранить порт для LibSodium"""
        self.set('libsodium_port', port)
    
    def get_libsodium_msg_mode(self) -> bool:
        """Получить состояние режима сообщений для LibSodium"""
        return self.get('libsodium_msg_mode', False)
    
    def set_libsodium_msg_mode(self, enabled: bool):
        """Сохранить состояние режима сообщений для LibSodium"""
        self.set('libsodium_msg_mode', enabled)
    
    # === Специфичные методы для Custom Codec ===
    
    def get_custom_csv(self) -> str:
        """Получить последний выбранный CSV для Custom Codec"""
        return self.get('custom_csv', '')
    
    def set_custom_csv(self, csv_name: str):
        """Сохранить выбранный CSV для Custom Codec"""
        self.set('custom_csv', csv_name)
    
    def get_custom_M(self) -> int:
        """Получить последнее значение M"""
        return self.get('custom_M', CODEC_M_DEFAULT)
    
    def set_custom_M(self, M: int):
        """Сохранить значение M"""
        self.set('custom_M', M)
    
    def get_custom_Q(self) -> int:
        """Получить последнее значение Q"""
        return self.get('custom_Q', CODEC_Q_DEFAULT)
    
    def set_custom_Q(self, Q: int):
        """Сохранить значение Q"""
        self.set('custom_Q', Q)
    
    def get_custom_funType(self) -> int:
        """Получить последний тип функции"""
        return self.get('custom_funType', 1)
    
    def set_custom_funType(self, funType: int):
        """Сохранить тип функции"""
        self.set('custom_funType', funType)
    
    def get_custom_h1(self) -> int:
        """Получить последнее значение h1"""
        return self.get('custom_h1', CODEC_H1_DEFAULT)
    
    def set_custom_h1(self, h1: int):
        """Сохранить значение h1"""
        self.set('custom_h1', h1)
    
    def get_custom_h2(self) -> int:
        """Получить последнее значение h2"""
        return self.get('custom_h2', CODEC_H2_DEFAULT)
    
    def set_custom_h2(self, h2: int):
        """Сохранить значение h2"""
        self.set('custom_h2', h2)
    
    def get_custom_encrypt_ip(self) -> str:
        """Получить последний использованный IP для Custom Codec Encrypt"""
        return self.get('custom_encrypt_ip', '')
    
    def set_custom_encrypt_ip(self, ip: str):
        """Сохранить IP для Custom Codec Encrypt"""
        self.set('custom_encrypt_ip', ip)
    
    def get_custom_port(self) -> int:
        """Получить последний использованный порт для Custom Codec"""
        return self.get('custom_port', DEFAULT_PORT)
    
    def set_custom_port(self, port: int):
        """Сохранить порт для Custom Codec"""
        self.set('custom_port', port)
    
    def get_custom_msg_mode(self) -> bool:
        """Получить состояние режима сообщений для Custom Codec"""
        return self.get('custom_msg_mode', False)
    
    def set_custom_msg_mode(self, enabled: bool):
        """Сохранить состояние режима сообщений для Custom Codec"""
        self.set('custom_msg_mode', enabled)
    
    def get_custom_auto_q(self) -> bool:
        """Получить состояние чекбокса 'Авто из CSV'"""
        return self.get('custom_auto_q', True)
    
    def set_custom_auto_q(self, enabled: bool):
        """Сохранить состояние чекбокса 'Авто из CSV'"""
        self.set('custom_auto_q', enabled)
    
    def get_custom_debug(self) -> bool:
        """Получить состояние режима отладки"""
        return self.get('custom_debug', False)
    
    def set_custom_debug(self, enabled: bool):
        """Сохранить состояние режима отладки"""
        self.set('custom_debug', enabled)
    
    def get_custom_debug_stats(self) -> bool:
        """Получить состояние сбора статистики"""
        return self.get('custom_debug_stats', False)
    
    def set_custom_debug_stats(self, enabled: bool):
        """Сохранить состояние сбора статистики"""
        self.set('custom_debug_stats', enabled)
    
    def get_custom_inject_errors(self) -> bool:
        """Получить состояние внесения ошибок"""
        return self.get('custom_inject_errors', False)
    
    def set_custom_inject_errors(self, enabled: bool):
        """Сохранить состояние внесения ошибок"""
        self.set('custom_inject_errors', enabled)
    
    def get_custom_error_rate(self) -> float:
        """Получить вероятность ошибки (в процентах)"""
        return self.get('custom_error_rate', 1.0)
    
    def set_custom_error_rate(self, rate: float):
        """Сохранить вероятность ошибки (в процентах)"""
        self.set('custom_error_rate', rate)
    
    # === Методы для файлового режима ===
    
    def get_last_file_dir(self) -> str:
        """Получить последнюю директорию выбора файла"""
        return self.get('last_file_dir', os.path.expanduser('~'))
    
    def set_last_file_dir(self, directory: str):
        """Сохранить последнюю директорию выбора файла"""
        self.set('last_file_dir', directory)
    
    def get_last_output_dir(self) -> str:
        """Получить последнюю директорию сохранения файла"""
        return self.get('last_output_dir', os.path.expanduser('~'))
    
    def set_last_output_dir(self, directory: str):
        """Сохранить последнюю директорию сохранения файла"""
        self.set('last_output_dir', directory)

