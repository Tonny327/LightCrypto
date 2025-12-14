cmake_minimum_required(VERSION 3.10)
project(LightCrypto)

set(CMAKE_CXX_STANDARD 17)

# Находим библиотеку потоков
find_package(Threads REQUIRED)

# Находим libsodium через pkg-config
find_package(PkgConfig REQUIRED)
pkg_check_modules(SODIUM REQUIRED libsodium)

include_directories(${SODIUM_INCLUDE_DIRS})
link_directories(${SODIUM_LIBRARY_DIRS})

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

# Компилируем tap_encrypt (с потоками)
add_executable(tap_encrypt src/tap_encrypt.cpp)
target_link_libraries(tap_encrypt ${SODIUM_LIBRARIES} Threads::Threads digitalcodec filetransfer)

# Компилируем tap_decrypt (с потоками)
add_executable(tap_decrypt src/tap_decrypt.cpp)
target_link_libraries(tap_decrypt ${SODIUM_LIBRARIES} Threads::Threads digitalcodec filetransfer)

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
