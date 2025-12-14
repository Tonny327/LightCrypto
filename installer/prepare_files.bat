@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
REM Скрипт подготовки файлов для установщика
REM Копирует все необходимые файлы в структуру для Inno Setup

echo ========================================
echo Подготовка файлов для установщика
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "BUILD_DIR=%PROJECT_ROOT%\build"
set "BUILD_RELEASE_DIR=%BUILD_DIR%\Release"
set "CIPHER_KEYS_DIR=%PROJECT_ROOT%\CipherKeys"
set "INSTALLER_DIR=%SCRIPT_DIR%"

REM Создаем структуру папок
set "STAGING_DIR=%INSTALLER_DIR%staging"
if exist "%STAGING_DIR%" rmdir /s /q "%STAGING_DIR%"
mkdir "%STAGING_DIR%"
mkdir "%STAGING_DIR%\bin"
mkdir "%STAGING_DIR%\CipherKeys"

echo [INFO] Копирование C++ исполняемых файлов...

REM Копируем C++ исполняемые файлы
set "EXE_FILES=file_encode.exe file_decode.exe file_encode_plain.exe file_decode_plain.exe file_encode_hybrid.exe file_decode_hybrid.exe"
set "FILES_COPIED=0"
set "FILES_MISSING=0"

for %%f in (%EXE_FILES%) do (
    if exist "%BUILD_RELEASE_DIR%\%%f" (
        copy /Y "%BUILD_RELEASE_DIR%\%%f" "%STAGING_DIR%\bin\" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo [OK] Скопирован: %%f
            set /a FILES_COPIED+=1
        ) else (
            echo [ERROR] Ошибка копирования: %%f
            set /a FILES_MISSING+=1
        )
    ) else if exist "%BUILD_DIR%\%%f" (
        copy /Y "%BUILD_DIR%\%%f" "%STAGING_DIR%\bin\" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo [OK] Скопирован: %%f
            set /a FILES_COPIED+=1
        ) else (
            echo [ERROR] Ошибка копирования: %%f
            set /a FILES_MISSING+=1
        )
    ) else (
        echo [WARNING] Файл не найден: %%f
        set /a FILES_MISSING+=1
    )
)

echo.
echo [INFO] Копирование libsodium.dll...

REM Копируем libsodium.dll
if exist "%BUILD_RELEASE_DIR%\libsodium.dll" (
    copy /Y "%BUILD_RELEASE_DIR%\libsodium.dll" "%STAGING_DIR%\bin\" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Скопирован: libsodium.dll
    ) else (
        echo [ERROR] Ошибка копирования libsodium.dll
    )
) else if exist "%BUILD_DIR%\libsodium.dll" (
    copy /Y "%BUILD_DIR%\libsodium.dll" "%STAGING_DIR%\bin\" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Скопирован: libsodium.dll
    ) else (
        echo [ERROR] Ошибка копирования libsodium.dll
    )
) else (
    echo [WARNING] libsodium.dll не найден
)

echo.
echo [INFO] Копирование CSV файлов...

REM Копируем CSV файлы
if exist "%CIPHER_KEYS_DIR%" (
    xcopy /E /I /Y "%CIPHER_KEYS_DIR%\*.csv" "%STAGING_DIR%\CipherKeys\" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] CSV файлы скопированы
    ) else (
        echo [WARNING] Ошибка копирования CSV файлов
    )
) else (
    echo [WARNING] Папка CipherKeys не найдена
)

echo.
echo ========================================
echo Подготовка завершена
echo ========================================
echo.
echo Скопировано исполняемых файлов: %FILES_COPIED%
echo Отсутствует файлов: %FILES_MISSING%
echo.
echo Файлы подготовлены в: %STAGING_DIR%
echo.

if %FILES_MISSING% GTR 0 (
    echo [WARNING] Некоторые файлы отсутствуют!
    echo Убедитесь, что сборка C++ компонентов завершена успешно.
    echo Запустите: build_windows.bat
    echo.
)

endlocal

