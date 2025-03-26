# 🔐 LightCrypto

  В проекте реализован алгоритм симметричного шифрования с автоматическим согласованием ключа на базе ECDH (Curve25519, реализация через библиотеку libsodium). 
  Обмен публичными ключами производится через сокет, после чего вычисляется общий секрет с помощью X25519. 
  Полученный ключ используется в алгоритме AEAD ChaCha20-Poly1305 для шифрования и аутентификации Ethernet-кадров.
  
## 📁 Структура проекта

```
src/
├── tap_encrypt.cpp     // Шифрует и отправляет кадры
├── tap_decrypt.cpp     // Принимает и расшифровывает кадры
├── test_speed.cpp      // Тестирует производительность шифрования
build/                  // Сюда собираются исполняемые файлы
create_taps.sh          // Скрипт создания TAP-интерфейсов
  
## 🚀 Как запустить

```bash
# 1. Установи зависимости
sudo apt install libsodium-dev

# 2. Создай TAP-интерфейсы с помощью скрипта
sudo ./create_taps.sh

# 3. Скомпилируй
mkdir -p build
g++ -g src/tap_encrypt.cpp -lsodium -o build/tap_encrypt
g++ -g src/tap_decrypt.cpp -lsodium -o build/tap_decrypt

# 4. Запусти (в двух терминалах)
sudo ./build/tap_decrypt
sudo ./build/tap_encrypt

