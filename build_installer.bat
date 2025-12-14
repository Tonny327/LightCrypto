@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
REM Главный скрипт сборки установщика LightCrypto для Windows
REM Автоматизирует весь процесс: сборка C++, PyInstaller, Inno Setup

echo ========================================
echo LightCrypto - Сборка установщика
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "INSTALLER_DIR=%PROJECT_ROOT%installer"
set "DIST_DIR=%PROJECT_ROOT%dist"
set "BUILD_DIR=%PROJECT_ROOT%build"

REM Проверка наличия необходимых инструментов
echo [INFO] Проверка инструментов...
echo.

REM Проверка Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python не найден в PATH
    echo Установите Python 3.8+: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python найден
python --version
echo.

REM Проверка PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] PyInstaller не установлен
    echo [INFO] Установка PyInstaller...
    python -m pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Не удалось установить PyInstaller
        pause
        exit /b 1
    )
    REM Повторная проверка после установки
    python -c "import PyInstaller" >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] PyInstaller установлен, но не может быть импортирован
        pause
        exit /b 1
    )
)
echo [OK] PyInstaller найден
echo.

REM Проверка Inno Setup
set "INNO_SETUP_PATH="
echo [INFO] Поиск Inno Setup Compiler...

REM Проверка через where (если в PATH)
where iscc >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "delims=" %%i in ('where iscc') do (
        set "INNO_SETUP_PATH=%%i"
    )
    if defined INNO_SETUP_PATH (
        echo [OK] Inno Setup найден через PATH
        goto :inno_found
    )
)

REM Поиск через PowerShell в стандартных местах (версии 5 и 6)
powershell -Command "if (Test-Path 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe') { Write-Output 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'; exit 0 } elseif (Test-Path 'C:\Program Files\Inno Setup 6\ISCC.exe') { Write-Output 'C:\Program Files\Inno Setup 6\ISCC.exe'; exit 0 } elseif (Test-Path 'C:\Program Files (x86)\Inno Setup 5\ISCC.exe') { Write-Output 'C:\Program Files (x86)\Inno Setup 5\ISCC.exe'; exit 0 } elseif (Test-Path 'C:\Program Files\Inno Setup 5\ISCC.exe') { Write-Output 'C:\Program Files\Inno Setup 5\ISCC.exe'; exit 0 } else { exit 1 }" > "%TEMP%\inno_path.txt" 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "delims=" %%p in ('type "%TEMP%\inno_path.txt"') do (
        set "INNO_SETUP_PATH=%%p"
    )
    if defined INNO_SETUP_PATH (
        echo [OK] Inno Setup найден: !INNO_SETUP_PATH!
        del "%TEMP%\inno_path.txt" >nul 2>&1
        goto :inno_found
    )
)
del "%TEMP%\inno_path.txt" >nul 2>&1

REM Если не найден, предлагаем ввести путь вручную
echo [WARNING] Inno Setup не найден автоматически
echo.
echo Установите Inno Setup: https://jrsoftware.org/isdl.php
echo Укажите путь к папке Inno Setup или к ISCC.exe:
set /p "MANUAL_PATH=Путь: "
if defined MANUAL_PATH (
    REM Удаляем кавычки, если они есть
    set "MANUAL_PATH=!MANUAL_PATH:"=!"
    REM Убираем пробелы в начале и конце
    for /f "tokens=*" %%a in ("!MANUAL_PATH!") do set "MANUAL_PATH=%%a"
    
    REM Если указана папка, добавляем ISCC.exe
    if exist "!MANUAL_PATH!\ISCC.exe" (
        set "INNO_SETUP_PATH=!MANUAL_PATH!\ISCC.exe"
        echo [OK] Найден ISCC.exe в указанной папке: !INNO_SETUP_PATH!
        goto :inno_found
    )
    REM Если указан файл напрямую
    if exist "!MANUAL_PATH!" (
        REM Проверяем, что это ISCC.exe
        echo "!MANUAL_PATH!" | findstr /i "iscc.exe" >nul
        if !ERRORLEVEL! EQU 0 (
            set "INNO_SETUP_PATH=!MANUAL_PATH!"
            echo [OK] Используется путь: !INNO_SETUP_PATH!
            goto :inno_found
        ) else (
            echo [ERROR] Указанный файл не является ISCC.exe: !MANUAL_PATH!
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR] Указанный путь не существует: !MANUAL_PATH!
        pause
        exit /b 1
    )
) else (
    echo [ERROR] Inno Setup необходим для создания установщика
    pause
    exit /b 1
)

:inno_found
if not defined INNO_SETUP_PATH (
    echo [ERROR] Критическая ошибка: INNO_SETUP_PATH не установлена
    pause
    exit /b 1
)
echo.

REM Проверка наличия собранных C++ файлов
echo [INFO] Проверка C++ исполняемых файлов...
set "EXE_FILES=file_encode.exe file_decode.exe file_encode_plain.exe file_decode_plain.exe file_encode_hybrid.exe file_decode_hybrid.exe"
set "FILES_FOUND=0"
set "FILES_MISSING=0"

for %%f in (%EXE_FILES%) do (
    if exist "%BUILD_DIR%\Release\%%f" (
        set /a FILES_FOUND+=1
    ) else if exist "%BUILD_DIR%\%%f" (
        set /a FILES_FOUND+=1
    ) else (
        set /a FILES_MISSING+=1
        echo [WARNING] Файл не найден: %%f
    )
)

if %FILES_MISSING% GTR 0 (
    echo [WARNING] Некоторые C++ файлы отсутствуют
    echo [INFO] Запуск сборки C++ компонентов...
    echo.
    call "%PROJECT_ROOT%build_windows.bat"
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Ошибка сборки C++ компонентов
        pause
        exit /b 1
    )
    echo.
)

echo [OK] C++ исполняемые файлы готовы
echo.

REM Шаг 1: Подготовка файлов
echo ========================================
echo Шаг 1: Подготовка файлов
echo ========================================
echo.
call "%INSTALLER_DIR%\prepare_files.bat"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ошибка подготовки файлов
    pause
    exit /b 1
)
echo.

REM Шаг 2: Сборка PyInstaller bundle
echo ========================================
echo Шаг 2: Сборка PyInstaller bundle
echo ========================================
echo.

REM Очистка предыдущей сборки
if exist "%DIST_DIR%\LightCrypto" (
    echo [INFO] Очистка предыдущей сборки...
    rmdir /s /q "%DIST_DIR%\LightCrypto" >nul 2>&1
)

REM Установка зависимостей Python
echo [INFO] Проверка Python зависимостей...
pip install -q -r "%PROJECT_ROOT%requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ошибка установки зависимостей
    pause
    exit /b 1
)
echo [OK] Зависимости установлены
echo.

REM Запуск PyInstaller
echo [INFO] Запуск PyInstaller...
cd /d "%PROJECT_ROOT%"
python -m PyInstaller --clean --noconfirm LightCrypto.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ошибка сборки PyInstaller
    pause
    exit /b 1
)
echo [OK] PyInstaller bundle создан
echo.

REM Шаг 3: Компиляция Inno Setup скрипта
echo ========================================
echo Шаг 3: Компиляция установщика
echo ========================================
echo.

REM Проверка наличия PyInstaller bundle
if not exist "%DIST_DIR%\LightCrypto\LightCrypto.exe" (
    echo [ERROR] PyInstaller bundle не найден: %DIST_DIR%\LightCrypto\LightCrypto.exe
    pause
    exit /b 1
)

REM Компиляция Inno Setup скрипта
echo [INFO] Компиляция Inno Setup скрипта...
cd /d "%INSTALLER_DIR%"
if not defined INNO_SETUP_PATH (
    echo [ERROR] INNO_SETUP_PATH не установлена
    pause
    exit /b 1
)
"%INNO_SETUP_PATH%" LightCrypto.iss
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Ошибка компиляции Inno Setup скрипта
    echo Проверьте, что все файлы подготовлены в staging/
    pause
    exit /b 1
)
cd /d "%PROJECT_ROOT%"
echo.

REM Проверка результата
if exist "%DIST_DIR%\LightCrypto_Setup.exe" (
    echo ========================================
    echo [SUCCESS] Установщик создан успешно!
    echo ========================================
    echo.
    echo Файл установщика: %DIST_DIR%\LightCrypto_Setup.exe
    echo.
    
    REM Показываем размер файла
    for %%A in ("%DIST_DIR%\LightCrypto_Setup.exe") do (
        set "SIZE=%%~zA"
        set /a SIZE_MB=!SIZE!/1024/1024
        echo Размер установщика: !SIZE_MB! MB
    )
    echo.
) else (
    echo [ERROR] Установщик не найден после компиляции
    pause
    exit /b 1
)

echo ========================================
echo Сборка завершена!
echo ========================================
echo.
echo Следующие шаги:
echo 1. Протестируйте установщик на чистой системе Windows
echo 2. Проверьте работу всех режимов (Plain, Custom Codec, Hybrid)
echo 3. Убедитесь, что все файлы установлены корректно
echo.
pause

