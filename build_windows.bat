@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
REM Build script for LightCrypto on Windows
REM Requires: CMake, MinGW-w64 or MSVC, libsodium

echo ========================================
echo LightCrypto - Windows Build
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

echo [OK] CMake found
cmake --version
echo.

REM Try to initialize Visual Studio environment first (preferred)
set VS_INITIALIZED=0
set GENERATOR=
set COMPILER_FOUND=0

REM Try to find and initialize Visual Studio first
echo [INFO] Searching for Visual Studio...

REM Check various VS versions and paths (2022, 2019, 2017)
set "VS_FOUND=0"
set "VS_PATH="

REM Visual Studio 2022
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)

REM Visual Studio 2019
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)

REM Visual Studio 2017
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    set "VS_FOUND=1"
    goto :init_vs
)

REM If VS not found, check if cl is already available
where cl >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Compiler cl already available in PATH
    set GENERATOR=Visual Studio 17 2022
    set COMPILER_FOUND=1
    goto :compiler_found
)

REM If VS not found, try MinGW
if %COMPILER_FOUND% EQU 0 (
    echo [INFO] Visual Studio not found, trying MinGW...
    where g++ >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        where mingw32-make >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [INFO] Found MinGW (g++ and mingw32-make)
            set GENERATOR=MinGW Makefiles
            set COMPILER_FOUND=1
            goto :compiler_found
        )
        where make >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [INFO] Found MinGW (g++ and make)
            set GENERATOR=MinGW Makefiles
            set COMPILER_FOUND=1
            goto :compiler_found
        )
        echo [WARNING] Found g++ but make/mingw32-make not found
        echo [WARNING] MinGW may not be properly configured
    )
)

REM If nothing found
goto :no_compiler

:init_vs
echo [INFO] Found Visual Studio: !VS_PATH!
echo [INFO] Initializing Visual Studio environment...
REM Call vcvars64.bat - it modifies environment variables
call "!VS_PATH!" >nul 2>&1
REM Check if cl is now available
where cl >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set GENERATOR=Visual Studio 17 2022
    set VS_INITIALIZED=1
    set COMPILER_FOUND=1
    echo [OK] Visual Studio environment initialized
    goto :compiler_found
) else (
    echo [WARNING] Failed to initialize VS environment or cl not found
    echo [INFO] VS initialization may have encoding issues
    echo [INFO] Try running from Developer Command Prompt for VS instead
    goto :no_compiler
)

:no_compiler
echo [ERROR] Compiler not found (g++ or cl)
echo.
echo Install one of the following:
echo 1. MinGW-w64: https://www.mingw-w64.org/downloads/
echo 2. Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/
echo    (select "Desktop development with C++")
echo.
echo If Visual Studio is installed but not found:
echo - Run script from "Developer Command Prompt for VS"
echo - Or check VS installation path
echo.
echo Alternative: use PowerShell and run:
echo   ^& "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
echo   .\build_windows.bat
pause
exit /b 1

:compiler_found
echo [INFO] Using generator: %GENERATOR%
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
cmake -G "%GENERATOR%" ..

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake configuration failed
    echo.
    echo Possible causes:
    echo 1. Compiler not properly configured
    echo 2. libsodium is not installed
    echo 3. Incorrect path to libsodium
    echo.
    if "%GENERATOR%"=="MinGW Makefiles" (
        echo MinGW-specific issues:
        echo - Make sure mingw32-make or make is in PATH
        echo - Try adding MinGW bin directory to PATH
        echo - Or use Visual Studio instead
        echo.
    )
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
echo   build\Release\  (for MSVC)
echo   build\          (for MinGW)
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
