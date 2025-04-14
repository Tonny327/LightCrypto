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

# Компилируем test_speed (без потоков)
add_executable(lightcrypto src/test_speed.cpp)
target_link_libraries(lightcrypto ${SODIUM_LIBRARIES})

# Компилируем tap_encrypt (с потоками)
add_executable(tap_encrypt src/tap_encrypt.cpp)
target_link_libraries(tap_encrypt ${SODIUM_LIBRARIES} Threads::Threads)

# Компилируем tap_decrypt (с потоками)
add_executable(tap_decrypt src/tap_decrypt.cpp)
target_link_libraries(tap_decrypt ${SODIUM_LIBRARIES} Threads::Threads)
