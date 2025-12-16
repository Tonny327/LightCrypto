# Инструкция по сборке установщика LightCrypto

## Быстрый старт

1. Убедитесь, что все C++ компоненты собраны:
   ```powershell
   .\build_windows.bat
   ```

2. Запустите сборку установщика:
   ```powershell
   .\build_installer.bat
   ```

3. Установщик будет создан в `dist/LightCrypto_Setup.exe`

## Требования

- Python 3.8+ с pip
- PyInstaller (`pip install pyinstaller`)
- Inno Setup 6.x (https://jrsoftware.org/isdl.php)
- Собранные C++ исполняемые файлы в `build/Release/`

## Что включает установщик

- Python runtime (встроенный, не требует установки Python)
- PyQt6 и все зависимости
- GUI приложение
- C++ исполняемые файлы (file_encode.exe, file_decode.exe и т.д.)
- libsodium.dll
- CSV файлы ключей (CipherKeys/)

## Структура после установки

```
C:\Program Files\LightCrypto\
├── LightCrypto.exe          # Главный исполняемый файл
├── _internal/               # PyInstaller внутренние файлы
├── bin/                     # C++ исполняемые файлы
│   ├── file_encode.exe
│   ├── file_decode.exe
│   ├── file_encode_plain.exe
│   ├── file_decode_plain.exe
│   ├── file_encode_hybrid.exe
│   ├── file_decode_hybrid.exe
│   └── libsodium.dll
└── CipherKeys/              # CSV файлы ключей
    ├── Q=2.csv
    └── ...
```

## Устранение проблем

### PyInstaller не найден
```powershell
pip install pyinstaller
```

### Inno Setup не найден
- Скачайте и установите Inno Setup 6.x
- Установите в стандартную папку: `C:\Program Files (x86)\Inno Setup 6\`

### C++ файлы не найдены
- Запустите `build_windows.bat` для сборки C++ компонентов
- Убедитесь, что файлы находятся в `build/Release/` или `build/`

### Ошибки при сборке PyInstaller
- Проверьте, что все зависимости установлены: `pip install -r requirements.txt`
- Убедитесь, что PyQt6 установлен: `pip install PyQt6`


