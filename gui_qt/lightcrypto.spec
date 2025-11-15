# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec файл для LightCrypto GUI
"""

import os
import sys

# Получаем абсолютные пути
# Определяем директорию spec файла - используем несколько методов для надежности
spec_dir = None

# Метод 1: SPECPATH (определен PyInstaller)
try:
    if 'SPECPATH' in globals() and SPECPATH:
        spec_dir = os.path.dirname(os.path.abspath(SPECPATH))
except:
    pass

# Метод 2: __file__ (если доступен)
if not spec_dir:
    try:
        if '__file__' in globals():
            spec_dir = os.path.dirname(os.path.abspath(__file__))
    except:
        pass

# Метод 3: текущая рабочая директория (должна быть gui_qt)
if not spec_dir:
    cwd = os.path.abspath(os.getcwd())
    # Проверяем, что мы в gui_qt (есть main.py)
    if os.path.exists(os.path.join(cwd, 'main.py')):
        spec_dir = cwd
    else:
        # Пробуем найти gui_qt относительно текущей директории
        for parent in [cwd, os.path.dirname(cwd), os.path.dirname(os.path.dirname(cwd))]:
            test_path = os.path.join(parent, 'gui_qt', 'main.py')
            if os.path.exists(test_path):
                spec_dir = os.path.join(parent, 'gui_qt')
                break

# Если все еще не определено, используем жестко закодированный путь
if not spec_dir:
    # Последняя попытка - предполагаем стандартную структуру
    # spec файл находится в gui_qt, ищем его родительскую директорию
    possible_paths = [
        '/home/tonny/projects/MyCryptoProject/LightCrypto/gui_qt',
        os.path.join(os.path.expanduser('~'), 'projects', 'MyCryptoProject', 'LightCrypto', 'gui_qt'),
    ]
    for path in possible_paths:
        if os.path.exists(os.path.join(path, 'main.py')):
            spec_dir = path
            break

if not spec_dir:
    raise RuntimeError("Не удалось определить директорию gui_qt! Убедитесь, что spec файл находится в gui_qt/")

# spec файл находится в gui_qt, поэтому project_root (LightCrypto) на уровень выше
project_root = os.path.abspath(os.path.join(spec_dir, '..'))
gui_qt_dir = spec_dir
build_dir = os.path.join(project_root, 'build')
cipher_keys_dir = os.path.join(project_root, 'CipherKeys')

# Проверка: если project_root не содержит LightCrypto, значит что-то не так
# Это может произойти, если spec_dir определяется неправильно
if 'LightCrypto' not in project_root:
    # Пробуем найти LightCrypto в пути spec_dir
    parts = spec_dir.split(os.sep)
    if 'LightCrypto' in parts:
        lightcrypto_idx = parts.index('LightCrypto')
        project_root = os.sep.join(parts[:lightcrypto_idx + 1])
        build_dir = os.path.join(project_root, 'build')
        cipher_keys_dir = os.path.join(project_root, 'CipherKeys')

block_cipher = False

# Абсолютный путь к main.py
main_py_path = os.path.join(gui_qt_dir, 'main.py')
if not os.path.exists(main_py_path):
    # Если не найден, попробуем найти относительно текущей директории
    main_py_path = os.path.abspath('main.py')
    if not os.path.exists(main_py_path):
        raise FileNotFoundError(f"main.py не найден! Искали: {os.path.join(gui_qt_dir, 'main.py')} и {main_py_path}")

a = Analysis(
    [main_py_path],
    pathex=[gui_qt_dir, project_root],
    binaries=[
        # Исполняемые файлы из build/
        (os.path.join(build_dir, 'tap_encrypt'), 'build'),
        (os.path.join(build_dir, 'tap_decrypt'), 'build'),
    ],
    datas=[
        # CSV файлы с ключами шифрования
        (cipher_keys_dir, 'CipherKeys'),
        # Скрипты setup
        (os.path.join(project_root, 'setup_tap_A.sh'), '.'),
        (os.path.join(project_root, 'setup_tap_B.sh'), '.'),
        (os.path.join(project_root, 'setup_tap_pair.sh'), '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='lightcrypto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Без консольного окна (GUI приложение)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Можно добавить иконку: icon='path/to/icon.ico'
)

