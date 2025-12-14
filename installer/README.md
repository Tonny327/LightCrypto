# LightCrypto Installer

Этот каталог содержит файлы для создания установщика Windows.

## Структура

- `LightCrypto.iss` - Скрипт Inno Setup для создания установщика
- `prepare_files.bat` - Скрипт подготовки файлов перед сборкой
- `staging/` - Временная папка с подготовленными файлами (создается автоматически)

## Требования для сборки установщика

1. **Python 3.8+** с установленными зависимостями:
   ```powershell
   pip install -r ..\requirements.txt
   ```

2. **PyInstaller**:
   ```powershell
   pip install pyinstaller
   ```

3. **Inno Setup 6.x**:
   - Скачать с https://jrsoftware.org/isdl.php
   - Установить в стандартную папку: `C:\Program Files (x86)\Inno Setup 6\`

4. **Собранные C++ компоненты**:
   - Запустите `build_windows.bat` для сборки всех исполняемых файлов
   - Файлы должны быть в `build/Release/` или `build/`

## Сборка установщика

Запустите главный скрипт из корня проекта:

```powershell
.\build_installer.bat
```

Скрипт автоматически:
1. Проверит наличие всех инструментов
2. Подготовит файлы (C++ exe, dll, CSV)
3. Соберет PyInstaller bundle
4. Создаст установщик через Inno Setup

Результат будет в `dist/LightCrypto_Setup.exe`

## Что включает установщик

- Python runtime (встроенный)
- PyQt6 и все зависимости
- GUI приложение (gui_qt/)
- C++ исполняемые файлы (в папке bin/)
- libsodium.dll
- CSV файлы ключей (CipherKeys/)

## Установка

После запуска установщика:
- Приложение будет установлено в `C:\Program Files\LightCrypto\`
- Создастся ярлык в меню Пуск
- Опционально: ярлык на рабочем столе

## Удаление

Удаление через "Установка и удаление программ" в Windows.

