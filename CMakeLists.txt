cmake_minimum_required(VERSION 3.10)

# Настройка vcpkg (если установлен)
if(DEFINED ENV{VCPKG_ROOT})
    set(CMAKE_TOOLCHAIN_FILE "$ENV{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake" CACHE STRING "")
elseif(EXISTS "D:/cripto/MyCryptoProject/vcpkg/scripts/buildsystems/vcpkg.cmake")
    set(CMAKE_TOOLCHAIN_FILE "D:/cripto/MyCryptoProject/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "")
endif()

project(LightCrypto)

set(CMAKE_CXX_STANDARD 17)

# Находим библиотеку потоков
find_package(Threads REQUIRED)

# Находим libsodium (кроссплатформенный способ)
if(WIN32)
    # Сначала пробуем найти через vcpkg (если используется)
    find_package(libsodium CONFIG QUIET)
    if(libsodium_FOUND)
        message(STATUS "Found libsodium via vcpkg")
        # Используем импортированные цели vcpkg
        set(SODIUM_INCLUDE_DIRS ${libsodium_INCLUDE_DIRS})
        set(SODIUM_LIBRARIES libsodium::libsodium)
    else()
        # Fallback: ручной поиск
        find_path(SODIUM_INCLUDE_DIR sodium.h
            PATHS
            ${CMAKE_SOURCE_DIR}/third_party/libsodium/include
            ${CMAKE_SOURCE_DIR}/libsodium/include
            "C:/libsodium/include"
            "C:/Program Files/libsodium/include"
            "$ENV{VCPKG_ROOT}/installed/x64-windows/include"
            "$ENV{VCPKG_ROOT}/installed/x86-windows/include"
        )
        find_library(SODIUM_LIBRARY
            NAMES sodium libsodium
            PATHS
            ${CMAKE_SOURCE_DIR}/third_party/libsodium/lib
            ${CMAKE_SOURCE_DIR}/libsodium/lib
            "C:/libsodium/lib"
            "C:/Program Files/libsodium/lib"
            "$ENV{VCPKG_ROOT}/installed/x64-windows/lib"
            "$ENV{VCPKG_ROOT}/installed/x86-windows/lib"
        )
        if(SODIUM_INCLUDE_DIR AND SODIUM_LIBRARY)
            set(SODIUM_INCLUDE_DIRS ${SODIUM_INCLUDE_DIR})
            set(SODIUM_LIBRARIES ${SODIUM_LIBRARY})
            include_directories(${SODIUM_INCLUDE_DIRS})
            message(STATUS "Found libsodium: ${SODIUM_LIBRARY}")
        else()
            message(FATAL_ERROR "libsodium not found! Please install libsodium for Windows.")
            message(FATAL_ERROR "Options:")
            message(FATAL_ERROR "  1. Install via vcpkg: vcpkg install libsodium:x64-windows")
            message(FATAL_ERROR "  2. Download from https://download.libsodium.org/libsodium/releases/")
            message(FATAL_ERROR "  3. Extract to C:\\libsodium\\")
        endif()
    endif()
else()
    # Для Linux используем pkg-config
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(SODIUM REQUIRED libsodium)
    include_directories(${SODIUM_INCLUDE_DIRS})
    link_directories(${SODIUM_LIBRARY_DIRS})
endif()

# Digital codec library (header-only-ish, but compile unit for linkage)
add_library(digitalcodec STATIC
    src/digital_codec.cpp
)
target_include_directories(digitalcodec PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

# File transfer library
add_library(filetransfer STATIC
    src/file_transfer.cpp
)
target_include_directories(filetransfer PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(filetransfer ${SODIUM_LIBRARIES})

# Компилируем test_speed (без потоков)
add_executable(lightcrypto src/test_speed.cpp)
target_link_libraries(lightcrypto ${SODIUM_LIBRARIES})

# TAP интерфейсы только для Linux (опционально)
if(UNIX AND NOT WIN32)
    # Компилируем tap_encrypt (с потоками) - только для Linux
    add_executable(tap_encrypt src/tap_encrypt.cpp)
    target_link_libraries(tap_encrypt ${SODIUM_LIBRARIES} Threads::Threads digitalcodec filetransfer)
    
    # Компилируем tap_decrypt (с потоками) - только для Linux
    add_executable(tap_decrypt src/tap_decrypt.cpp)
    target_link_libraries(tap_decrypt ${SODIUM_LIBRARIES} Threads::Threads digitalcodec filetransfer)
endif()

# Компилируем file_encode (локальное кодирование файлов)
add_executable(file_encode src/file_encode.cpp)
target_link_libraries(file_encode ${SODIUM_LIBRARIES} digitalcodec filetransfer)

# Компилируем file_decode (локальное декодирование файлов)
add_executable(file_decode src/file_decode.cpp)
target_link_libraries(file_decode ${SODIUM_LIBRARIES} digitalcodec filetransfer)

# Компилируем file_encode_plain (локальное кодирование БЕЗ шифрования)
add_executable(file_encode_plain src/file_encode_plain.cpp)
target_link_libraries(file_encode_plain filetransfer digitalcodec ${SODIUM_LIBRARIES})

# Компилируем file_decode_plain (локальное декодирование БЕЗ шифрования)
add_executable(file_decode_plain src/file_decode_plain.cpp)
target_link_libraries(file_decode_plain filetransfer digitalcodec ${SODIUM_LIBRARIES})

# Компилируем file_encode_hybrid (гибридное кодирование: DigitalCodec + plain фрагментация)
add_executable(file_encode_hybrid src/file_encode_hybrid.cpp)
target_link_libraries(file_encode_hybrid filetransfer digitalcodec ${SODIUM_LIBRARIES})

# Компилируем file_decode_hybrid (гибридное декодирование: plain поиск + DigitalCodec расшифровка)
add_executable(file_decode_hybrid src/file_decode_hybrid.cpp)
target_link_libraries(file_decode_hybrid filetransfer digitalcodec ${SODIUM_LIBRARIES})
