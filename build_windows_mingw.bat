@echo off
REM Скрипт сборки LightCrypto для Windows с MinGW-w64
REM Требуется: CMake, MinGW-w64, libsodium

echo ========================================
echo LightCrypto - Сборка для Windows (MinGW)
echo ========================================
echo.

REM Проверка наличия CMake
where cmake >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] CMake не найден в PATH!
    pause
    exit /b 1
)

REM Проверка наличия MinGW
where g++ >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] MinGW-w64 не найден в PATH!
    echo Установите MinGW-w64: https://www.mingw-w64.org/
    pause
    exit /b 1
)

echo [OK] Инструменты найдены
echo.

REM Создание директории build
if not exist build mkdir build
cd build

echo [INFO] Конфигурация проекта...
cmake -G "MinGW Makefiles" ..

if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] Ошибка конфигурации CMake!
    echo Проверьте наличие libsodium
    pause
    exit /b 1
)

echo.
echo [INFO] Сборка проекта...
cmake --build . -j %NUMBER_OF_PROCESSORS%

if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] Ошибка сборки!
    pause
    exit /b 1
)

echo.
echo [УСПЕХ] Сборка завершена!
cd ..
pause



