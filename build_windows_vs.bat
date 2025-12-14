@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
REM Build script for LightCrypto on Windows
REM Run this from Developer Command Prompt for VS (where cl is already available)
REM Or run build_windows.bat which will try to auto-detect VS

echo ========================================
echo LightCrypto - Windows Build (Visual Studio)
echo ========================================
echo.

REM Check for CMake
where cmake >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake not found in PATH
    echo Install CMake: https://cmake.org/download/
    pause
    exit /b 1
)

REM Check for cl compiler
where cl >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Visual Studio compiler (cl) not found
    echo Please run this script from Developer Command Prompt for VS
    echo Or use build_windows.bat which will try to initialize VS automatically
    pause
    exit /b 1
)

echo [OK] CMake found
cmake --version
echo.
echo [OK] Visual Studio compiler found
cl 2>nul | findstr /C:"Microsoft" >nul
if %ERRORLEVEL% EQU 0 (
    cl 2>nul | findstr /C:"version"
)
echo.

REM Clean build directory if it exists and has CMakeCache from different generator
if exist build\CMakeCache.txt (
    echo [INFO] Found existing CMake cache
    echo [INFO] Cleaning build directory to avoid generator conflicts...
    cd build
    if exist CMakeCache.txt del /q CMakeCache.txt >nul 2>&1
    if exist CMakeFiles rmdir /s /q CMakeFiles >nul 2>&1
    cd ..
)

REM Create build directory
if not exist build mkdir build
cd build

echo.
echo [INFO] Configuring project...
cmake -G "Visual Studio 17 2022" ..

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake configuration failed
    echo.
    echo Possible causes:
    echo 1. libsodium is not installed
    echo 2. Incorrect path to libsodium
    echo.
    echo Solutions for Windows:
    echo.
    echo Option 1 (recommended): Install via vcpkg
    echo   cd D:\cripto\MyCryptoProject\vcpkg
    echo   .\vcpkg install libsodium:x64-windows
    echo   set VCPKG_ROOT=D:\cripto\MyCryptoProject\vcpkg
    echo.
    echo Option 2: Manual installation
    echo   1. Download libsodium: https://download.libsodium.org/libsodium/releases/
    echo   2. Extract to C:\libsodium\
    echo   3. Structure should be: C:\libsodium\include\sodium.h
    echo                          C:\libsodium\lib\sodium.lib
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Building project...
cmake --build . --config Release

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Build completed!
echo ========================================
echo.
echo Executables are located in:
echo   build\Release\
echo.
echo Built programs:
echo   - file_encode.exe
echo   - file_decode.exe
echo   - file_encode_plain.exe
echo   - file_decode_plain.exe
echo   - file_encode_hybrid.exe
echo   - file_decode_hybrid.exe
echo.

cd ..
pause

