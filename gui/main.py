#!/usr/bin/env python3
"""
LightCrypto GUI - Главный файл запуска
Точка входа в приложение
"""

import sys
import os

# Добавляем текущую директорию в PATH для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import ConfigManager
from common.utils import check_sudo_access, check_build_files
from common.constants import MSG_SUDO_REQUIRED, MSG_BUILD_NOT_FOUND

from launcher import LauncherWindow
from role_selector import RoleSelectorWindow

# Импорты GUI (будут созданы позже)
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
        
        # Проверка системных требований
        if not self._check_requirements():
            sys.exit(1)
    
    def _check_requirements(self) -> bool:
        """Проверка системных требований"""
        import platform
        is_windows = platform.system() == 'Windows'
        
        print("🔍 Проверка системных требований...")
        
        # Проверка прав администратора (Windows) или sudo (Linux)
        if not check_sudo_access():
            if is_windows:
                print("⚠️  Требуются права администратора!")
                print("   Некоторые функции могут не работать без прав администратора.")
            else:
                print(MSG_SUDO_REQUIRED)
            response = input("Продолжить без прав администратора? (y/N): ")
            if response.lower() != 'y':
                return False
        else:
            if is_windows:
                print("✅ Права администратора: OK")
            else:
                print("✅ Sudo доступ: OK")
        
        # Проверка исполняемых файлов
        all_exist, missing = check_build_files()
        if not all_exist:
            print(MSG_BUILD_NOT_FOUND)
            print(f"Отсутствуют файлы: {', '.join(missing)}")
            response = input("Продолжить без исполняемых файлов? (y/N): ")
            if response.lower() != 'y':
                return False
        else:
            print("✅ Исполняемые файлы: OK")
        
        print("✅ Проверка завершена\n")
        return True
    
    def run(self):
        """Запуск приложения"""
        self.show_launcher()
    
    def show_launcher(self):
        """Показать стартовое окно выбора типа шифрования"""
        launcher = LauncherWindow(
            config=self.config,
            on_select=self.on_cipher_selected
        )
        launcher.run()
    
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
        role_selector = RoleSelectorWindow(
            config=self.config,
            cipher_type=self.current_cipher,
            on_select=self.on_role_selected,
            on_back=self.show_launcher
        )
        role_selector.run()
    
    def on_role_selected(self, cipher_type: str, role: str):
        """
        Обработка выбора роли
        
        Args:
            cipher_type: 'libsodium' или 'custom'
            role: 'encrypt' или 'decrypt'
        """
        self.current_cipher = cipher_type
        self.current_role = role
        
        # Открытие соответствующего GUI
        if cipher_type == 'libsodium' and role == 'encrypt':
            if LibSodiumEncryptGUI:
                self.show_libsodium_encrypt()
            else:
                print("❌ LibSodium Encrypt GUI еще не реализован")
        
        elif cipher_type == 'libsodium' and role == 'decrypt':
            if LibSodiumDecryptGUI:
                self.show_libsodium_decrypt()
            else:
                print("❌ LibSodium Decrypt GUI еще не реализован")
        
        elif cipher_type == 'custom' and role == 'encrypt':
            if CustomCodecEncryptGUI:
                self.show_custom_encrypt()
            else:
                print("❌ Custom Codec Encrypt GUI еще не реализован")
        
        elif cipher_type == 'custom' and role == 'decrypt':
            if CustomCodecDecryptGUI:
                self.show_custom_decrypt()
            else:
                print("❌ Custom Codec Decrypt GUI еще не реализован")
    
    def show_libsodium_encrypt(self):
        """Показать LibSodium Encrypt GUI"""
        gui = LibSodiumEncryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        gui.run()
    
    def show_libsodium_decrypt(self):
        """Показать LibSodium Decrypt GUI"""
        gui = LibSodiumDecryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        gui.run()
    
    def show_custom_encrypt(self):
        """Показать Custom Codec Encrypt GUI"""
        gui = CustomCodecEncryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        gui.run()
    
    def show_custom_decrypt(self):
        """Показать Custom Codec Decrypt GUI"""
        gui = CustomCodecDecryptGUI(
            config=self.config,
            on_back=self.show_role_selector
        )
        gui.run()


def main():
    """Точка входа"""
    print("""
╔═══════════════════════════════════════════════════╗
║           🔐 LightCrypto GUI v1.0.0              ║
║        Система защищенной передачи данных         ║
╚═══════════════════════════════════════════════════╝
    """)
    
    try:
        app = LightCryptoGUI()
        app.run()
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

