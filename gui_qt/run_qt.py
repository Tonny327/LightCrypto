#!/usr/bin/env python3
"""
Скрипт запуска LightCrypto GUI (PyQt6 версия)
"""

import sys
import os

# Добавляем текущую директорию в PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    from main import main
    main()

