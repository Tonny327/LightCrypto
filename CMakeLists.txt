cmake_minimum_required(VERSION 3.10)
project(LightCrypto)

set(CMAKE_CXX_STANDARD 17)

find_package(PkgConfig REQUIRED)
pkg_check_modules(SODIUM REQUIRED libsodium)

include_directories(${SODIUM_INCLUDE_DIRS})
link_directories(${SODIUM_LIBRARY_DIRS})

add_executable(lightcrypto src/test_speed.cpp)
target_link_libraries(lightcrypto ${SODIUM_LIBRARIES})

add_executable(tap_encrypt src/tap_encrypt.cpp)
target_link_libraries(tap_encrypt ${SODIUM_LIBRARIES})

add_executable(tap_decrypt src/tap_decrypt.cpp)
target_link_libraries(tap_decrypt ${SODIUM_LIBRARIES})
