# 🔐 LightCrypto

  В проекте реализован алгоритм симметричного шифрования с автоматическим согласованием ключа на базе ECDH (Curve25519, реализация через библиотеку libsodium). 
  Обмен публичными ключами производится через UDP-сокет, после чего вычисляется общий секрет с помощью X25519. 
  Полученный ключ используется в алгоритме AEAD ChaCha20-Poly1305 для шифрования и аутентификации Ethernet-кадров.
  
- [Структура проекта](#-структура-проекта)
- [Как запустить](#-как-запустить)
- [Тестирование в сетевых неймспейсах](#-тестирование-в-сетевых-неймспейсах)
- [Режим `--msg`](#️-отправка-сообщений-в-режиме---msg)
- [Режим передачи Ethernet-кадров](#-режим-передачи-ethernet-кадров-по-умолчанию)
- [Тест производительности](#-тест-производительности-шифрования)

---

## 📁 Структура проекта

```
src/
├── tap_encrypt.cpp     // Шифрует и отправляет кадры или сообщения (--msg)
├── tap_decrypt.cpp     // Принимает и расшифровывает кадры или сообщения (--msg)
├── test_speed.cpp      // Тестирует производительность шифрования
build/                  // Сюда собираются исполняемые файлы
setup_tap_pair.sh       // Скрипт создания TAP-интерфейсов
```
---

## 🚀 Как запустить


### 🛠 Требования

- **ОС**: Linux Ubuntu
- **Зависимости**: `libsodium-dev`, `iproute2`, `tcpdump`, `iputils-ping`
- **Права**: `sudo` для настройки сетевых неймспейсов и запуска программ

### 🛆 Установка зависимостей

```bash
sudo apt update
sudo apt install -y libsodium-dev iproute2 tcpdump iputils-ping iperf hping3
```

### 🔨 Сборка проекта

Скомпилируй программы:

```bash
mkdir -p build
g++ -o build/tap_encrypt src/tap_encrypt.cpp -lsodium -pthread
g++ -o build/tap_decrypt src/tap_decrypt.cpp -lsodium -pthread
```

(Опционально) Используй скрипт сборки:

```bash
bash rebuild.sh
```
---

## 🌐 Тестирование в сетевых неймспейсах

### 1. Настройка неймспейсов и интерфейсов

```bash
sudo ip netns delete ns1 2>/dev/null
sudo ip netns delete ns2 2>/dev/null
sudo killall tap_encrypt tap_decrypt tcpdump 2>/dev/null

sudo ip netns add ns1
sudo ip netns add ns2

sudo ip netns exec ns1 ip tuntap add dev tap0 mode tap
sudo ip netns exec ns1 ip addr add 10.0.0.1/24 dev tap0
sudo ip netns exec ns1 ip link set tap0 up

sudo ip netns exec ns2 ip tuntap add dev tap1 mode tap
sudo ip netns exec ns2 ip addr add 10.0.0.2/24 dev tap1
sudo ip netns exec ns2 ip link set tap1 up

sudo ip link add veth1 type veth peer name veth2
sudo ip link set veth1 netns ns1
sudo ip link set veth2 netns ns2
sudo ip netns exec ns1 ip addr add 192.168.1.1/24 dev veth1
sudo ip netns exec ns1 ip link set veth1 up
sudo ip netns exec ns2 ip addr add 192.168.1.2/24 dev veth2
sudo ip netns exec ns2 ip link set veth2 up

sudo ip netns exec ns1 ip route add default via 192.168.1.2
sudo ip netns exec ns2 ip route add default via 192.168.1.1

sudo ip netns exec ns1 sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo ip netns exec ns2 sysctl -w net.ipv6.conf.all.disable_ipv6=1
```

### 2. Запуск программ

**Терминал 1 (приёмник в ns2):**

```bash
sudo ip netns exec ns2 ./build/tap_decrypt 192.168.1.2 12345
```

**Терминал 2 (отправитель в ns1):**

```bash
sudo ip netns exec ns1 ./build/tap_encrypt 192.168.1.2 12345
```

### 3. Генерация трафика 
**с помощью ping:**

**Терминал 3:**

```bash
sudo ip netns exec ns1 ping 10.0.0.2
```

**Ожидаемый вывод:**
```bash
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.  
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.421 ms
```
Пинг должен показать успешную передачу, а в консолях программ — сообщения о кадрах (42 байта для ARP, 98 байт для ICMP).

### 🔁 Тестирование пропускной способности с iperf

#### TCP:
- **Терминал 3 - Сервер (в ns2):**
```bash
sudo ip netns exec ns2 iperf -s -B 10.0.0.2
```
- **Терминал 4 - Клиент (в ns1):**
```bash
sudo ip netns exec ns1 iperf -c 10.0.0.2 -t 10
```

#### UDP:
- **Терминал 3 - Сервер:**
```bash
sudo ip netns exec ns2 iperf -s -u -B 10.0.0.2
```
- **Терминал 4 - Клиент:**
```bash
sudo ip netns exec ns1 iperf -c 10.0.0.2 -u -t 10 -b 100M
```

**📈 Ожидаемый результат: в консолях tap_encrypt и tap_decrypt появятся сообщения, например:**

```bash
Отправлен зашифрованный кадр (1500 байт)
Принят и расшифрован кадр (1500 байт)
...
```

**iperf выведет пропускную способность, например:**
```bash
[  3]  0.0-10.0 sec  110.25 MBytes  103.07 Mbits/sec
```
---
### 🧨 Генерация трафика с помощью hping3

**Терминал 3 - TCP SYN-пакеты из ns1:**

```bash
sudo ip netns exec ns1 hping3 10.0.0.2 -S -p 80 -c 10
```

**Терминал 3 - TCP UDP-пакеты из ns1:**

```bash
sudo ip netns exec ns1 hping3 10.0.0.2 -2 -p 5000 -c 10
```
**📈 Ожидаемый результат:** в консолях tap_encrypt и tap_decrypt появятся сообщения, например:

```bash
Отправлен зашифрованный кадр (60 байт)
Принят и расшифрован кадр (60 байт)
```
hping3 покажет отправленные пакеты и возможные ответы.

### ✉️ Отправка сообщений в режиме `--msg`

#### Терминал 1 - приёмник в ns2:
```bash
sudo ip netns exec ns2 ./build/tap_decrypt --msg 192.168.1.2 12345
```

#### Терминал 2 - Отправитель в ns1:
```bash
sudo ip netns exec ns1 ./build/tap_encrypt --msg 192.168.1.2 12345
```

🖊️ Вводи текст в терминале отправителя — он будет зашифрован и появится в выводе приёмника.

✅ **Ожидаемый результат:** в консолях программ появятся сообщения, например:

**📥 Приёмник:**
```bash
Ожидание пакетов на IP: 192.168.1.2, порт: 12345
Публичный ключ отправителя получен
Получено сообщение: "Привет, LightCrypto!"
```

**📤 Отправитель:**
```bash
IP-адрес: 192.168.1.2, порт: 12345, начинаем работу...
Публичный ключ получателя получен
Отправлено сообщение: "Привет, LightCrypto!"

### 4. Остановка и очистка ресурсов

```bash
sudo ip netns delete ns1 2>/dev/null
sudo ip netns delete ns2 2>/dev/null
sudo killall tap_encrypt tap_decrypt tcpdump 2>/dev/null
```


---

## 📡 Режим передачи Ethernet-кадров (по умолчанию)

### 🖥 Локальный запуск (на одном ПК):

```bash
# Терминал 1:
sudo ./build/tap_decrypt

# Терминал 2:
sudo ./build/tap_encrypt
```

По умолчанию используется IP `127.0.0.1` и порт `12345`.

---

### 🌐 Запуск по сети (на двух устройствах):

#### На приёмнике (например, IP: 192.168.1.2):
```bash
sudo ./build/tap_decrypt 0.0.0.0 5555
```
или:
```bash
sudo ./build/tap_decrypt 5555
```

#### На отправителе:
```bash
sudo ./build/tap_encrypt 192.168.1.2 5555
```

---

## 💬 Режим передачи текстовых сообщений (`--msg`)

В этом режиме программы шифруют и передают строки, введённые вручную.

### 📥 Приёмник сообщений:

```bash
sudo ./build/tap_decrypt --msg
```

или с указанием порта:
```bash
sudo ./build/tap_decrypt --msg 5555
```

### 📤 Отправитель сообщений:

```bash
sudo ./build/tap_encrypt --msg
```

или с указанием IP и порта:
```bash
sudo ./build/tap_encrypt --msg 127.0.0.1 5555
```

> ✅ **Если не указывать IP и порт, по умолчанию используется** `127.0.0.1:12345`.

После запуска просто вводи текст в терминал отправителя — он будет зашифрован и отобразится на стороне приёмника.

---

## ✅ Проверка целостности кадров

В каждом отправляемом кадре (или сообщении) сначала вычисляется SHA-256 и добавляется 32‑байтовый хеш к данным перед шифрованием. На приёмной стороне после расшифровки эти первые 32 байта отделяются как «присланный хеш», а оставшийся блок проверяется заново через SHA-256. Если вычисленный хеш совпадает с присланным, кадр считается корректным и выводится сообщение «Хеши совпадают — кадр корректен». В противном случае кадр признаётся повреждённым и игнорируется. Такой подход позволяет отказаться от временных файлов и логов, делая проверку целостности «на лету» в самом пакете.

### Захват трафика (опционально):

```bash
# В ns1:
sudo ip netns exec ns1 tcpdump -i tap0 -v

# В ns2:
sudo ip netns exec ns2 tcpdump -i tap1 -v
```

---

## 📊 Тест производительности шифрования

Файл `test_speed.cpp` генерирует 10 МБ случайных данных, шифрует и расшифровывает их, измеряя скорость выполнения ChaCha20-Poly1305.

### 🔨 Сборка:

```bash
g++ -g src/test_speed.cpp -lsodium -o build/test_speed
```

### ▶️ Запуск:

```bash
./build/test_speed
```

### 📋 Пример вывода:

```
✅ Шифрование + расшифровка успешны
📦 Объём: 10 МБ
⚡ Скорость: 136.8 МБ/с
```

> 💡 Этот тест не использует TAP-интерфейсы и служит только для оценки производительности libsodium.

---
