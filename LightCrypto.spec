# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for LightCrypto GUI
Creates a one-directory bundle with all dependencies
"""

import os
import sys

# Get project root directory
# PyInstaller sets specpath, or we use current working directory
try:
    # Try to get from specpath (PyInstaller context)
    project_root = os.path.abspath(specpath)
except NameError:
    # Fallback to current working directory (should be project root)
    project_root = os.path.abspath(os.getcwd())
gui_root = os.path.join(project_root, 'gui_qt')
cipher_keys_dir = os.path.join(project_root, 'CipherKeys')
build_dir = os.path.join(project_root, 'build')
build_release_dir = os.path.join(build_dir, 'Release')

# Collect all data files
datas = []

# Add CipherKeys directory
if os.path.isdir(cipher_keys_dir):
    datas.append((cipher_keys_dir, 'CipherKeys'))

# Add C++ executables (will be copied to bin/ subdirectory)
binaries = []
exe_files = [
    'file_encode.exe',
    'file_decode.exe',
    'file_encode_plain.exe',
    'file_decode_plain.exe',
    'file_encode_hybrid.exe',
    'file_decode_hybrid.exe'
]

# Check for executables in Release directory first, then build directory
for exe_name in exe_files:
    exe_path_release = os.path.join(build_release_dir, exe_name)
    exe_path_build = os.path.join(build_dir, exe_name)
    
    if os.path.isfile(exe_path_release):
        binaries.append((exe_path_release, 'bin'))
    elif os.path.isfile(exe_path_build):
        binaries.append((exe_path_build, 'bin'))

# Add libsodium.dll if found
libsodium_dll_release = os.path.join(build_release_dir, 'libsodium.dll')
libsodium_dll_build = os.path.join(build_dir, 'libsodium.dll')

if os.path.isfile(libsodium_dll_release):
    binaries.append((libsodium_dll_release, 'bin'))
elif os.path.isfile(libsodium_dll_build):
    binaries.append((libsodium_dll_build, 'bin'))

# Hidden imports for PyQt6
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'PyQt6.QtNetwork',
    'PyQt6.sip',
]

a = Analysis(
    [os.path.join(gui_root, 'main.py')],
    pathex=[gui_root, project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',  # We use PyQt6, not tkinter
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable (onedir mode)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Important for onedir mode
    name='LightCrypto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Can add icon.ico here if available
)

# Collect all files into one directory (onedir mode)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LightCrypto',
)

