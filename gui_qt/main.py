#!/usr/bin/env python3
"""
LightCrypto GUI - Главный файл запуска (PyQt6)
Точка входа в приложение
"""

import sys
import os

# Добавляем текущую директорию в PATH для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from common.config import ConfigManager
from common.utils import check_sudo_access, check_build_files
from common.constants import MSG_SUDO_REQUIRED, MSG_BUILD_NOT_FOUND

from launcher import LauncherWindow
from role_selector import RoleSelectorWindow

# Импорты GUI
try:
    from libsodium.encrypt_window import LibSodiumEncryptGUI
    from libsodium.decrypt_window import LibSodiumDecryptGUI
    from custom.encrypt_window import CustomCodecEncryptGUI
    from custom.decrypt_window import CustomCodecDecryptGUI
except ImportError as e:
    print(f"⚠️  Предупреждение: Некоторые модули GUI еще не созданы: {e}")
    LibSodiumEncryptGUI = None
    LibSodiumDecryptGUI = None
    CustomCodecEncryptGUI = None
    CustomCodecDecryptGUI = None


class LightCryptoGUI:
    """
    Главный класс приложения
    Управляет навигацией между окнами
    """
    
    def __init__(self):
        self.config = ConfigManager()
        self.current_cipher = None
        self.current_role = None
        self.current_window = None
        
        # Проверка системных требований
        if not self._check_requirements():
            sys.exit(1)
    
    def _check_requirements(self) -> bool:
        """Проверка системных требований"""
        print("🔍 Проверка системных требований...")
        
        # Проверка sudo доступа (только для Linux)
        import os
        if os.name != 'nt':  # Не Windows
            if not check_sudo_access():
                print(MSG_SUDO_REQUIRED)
                print("⚠️  Продолжение без sudo может привести к ошибкам")
            else:
                print("✅ Sudo доступ: OK")
        else:
            print("✅ Windows: sudo не требуется")
        
        # Проверка исполняемых файлов
        all_exist, missing = check_build_files()
        if not all_exist:
            print("⚠️  Некоторые исполняемые файлы не найдены")
            print(f"Отсутствуют: {', '.join(missing)}")
            print("⚠️  Запустите сборку: build_windows.bat (Windows) или ./rebuild.sh (Linux)")
            print("⚠️  Продолжение без исполняемых файлов может привести к ошибкам")
        else:
            print("✅ Исполняемые файлы: OK")
        
        print("✅ Проверка завершена\n")
        return True
    
    def run(self):
        """Запуск приложения"""
        # Для Windows сразу показываем выбор роли для Custom Codec
        import os
        if os.name == 'nt':  # Windows
            self.current_cipher = 'custom'
            self.show_role_selector()
        else:
            # Для Linux показываем launcher
            self.show_launcher()
    
    def show_launcher(self):
        """Показать стартовое окно выбора типа шифрования"""
        if self.current_window:
            self.current_window.close()
        
        self.current_window = LauncherWindow(
            config=self.config,
            on_select=self.on_cipher_selected
        )
        self.current_window.show()
    
    def on_cipher_selected(self, cipher_type: str):
        """
        Обработка выбора типа шифрования
        
        Args:
            cipher_type: 'libsodium' или 'custom'
        """
        self.current_cipher = cipher_type
        self.show_role_selector()
    
    def show_role_selector(self):
        """Показать окно выбора роли"""
        if self.current_window:
            self.current_window.close()
        
        # Определяем callback для кнопки "Назад"
        import os
        if os.name == 'nt' and self.current_cipher == 'custom':
            # На Windows при прямом запуске Custom Codec - не показываем кнопку "Назад"
            on_back = None
        else:
            # Иначе показываем launcher
            on_back = self.show_launcher
        
        self.current_window = RoleSelectorWindow(
            config=self.config,
            cipher_type=self.current_cipher,
            on_select=self.on_role_selected,
            on_back=on_back
        )
        self.current_window.show()
    
    def on_role_selected(self, cipher_type: str, role: str):
        """
        Обработка выбора роли
        
        Args:
            cipher_type: 'libsodium' или 'custom'
            role: 'encrypt', 'decrypt', 'local_encode' или 'local_decode'
        """
        self.current_cipher = cipher_type
        self.current_role = role
        
        # Закрываем предыдущее окно
        if self.current_window:
            self.current_window.close()
        
        # Локальный режим (Windows)
        if role == 'local_encode':
            if CustomCodecEncryptGUI:
                self.show_custom_encrypt()
            else:
                QMessageBox.critical(None, "Ошибка", "Custom Codec Encrypt GUI еще не реализован")
            return
        
        if role == 'local_decode':
            if CustomCodecDecryptGUI:
                self.show_custom_decrypt()
            else:
                QMessageBox.critical(None, "Ошибка", "Custom Codec Decrypt GUI еще не реализован")
            return
        
        # Сетевой режим (Linux)
        if cipher_type == 'libsodium' and role == 'encrypt':
            if LibSodiumEncryptGUI:
                self.show_libsodium_encrypt()
            else:
                QMessageBox.critical(None, "Ошибка", "LibSodium Encrypt GUI еще не реализован")
        
        elif cipher_type == 'libsodium' and role == 'decrypt':
            if LibSodiumDecryptGUI:
                self.show_libsodium_decrypt()
            else:
                QMessageBox.critical(None, "Ошибка", "LibSodium Decrypt GUI еще не реализован")
        
        elif cipher_type == 'custom' and role == 'encrypt':
            if CustomCodecEncryptGUI:
                self.show_custom_encrypt()
            else:
                QMessageBox.critical(None, "Ошибка", "Custom Codec Encrypt GUI еще не реализован")
        
        elif cipher_type == 'custom' and role == 'decrypt':
            if CustomCodecDecryptGUI:
                self.show_custom_decrypt()
            else:
                QMessageBox.critical(None, "Ошибка", "Custom Codec Decrypt GUI еще не реализован")
    
    def show_libsodium_encrypt(self):
        """Показать LibSodium Encrypt GUI"""
        self.current_window = LibSodiumEncryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        self.current_window.show()
    
    def show_libsodium_decrypt(self):
        """Показать LibSodium Decrypt GUI"""
        self.current_window = LibSodiumDecryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        self.current_window.show()
    
    def show_custom_encrypt(self):
        """Показать Custom Codec Encrypt GUI"""
        self.current_window = CustomCodecEncryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        self.current_window.show()
    
    def show_custom_decrypt(self):
        """Показать Custom Codec Decrypt GUI"""
        self.current_window = CustomCodecDecryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        self.current_window.show()


def main():
    """Точка входа"""
    print("""
╔═══════════════════════════════════════════════════╗
║           🔐 LightCrypto GUI v2.0.0 (PyQt6)      ║
║        Система защищенной передачи данных         ║
╚═══════════════════════════════════════════════════╝
    """)
    
    # Создание QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("LightCrypto")
    
    try:
        gui = LightCryptoGUI()
        gui.run()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\n⚠️  Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

