#!/bin/bash
set -e

echo "🧹 Удаляем старые неймспейсы (если остались)..."
sudo ip netns del sender 2>/dev/null || true
sudo ip netns del receiver 2>/dev/null || true
sudo ip link delete veth0 2>/dev/null || true

echo "🔧 Создаём сетевые неймспейсы..."
sudo ip netns add sender
sudo ip netns add receiver

echo "🔗 Создаём veth-пару..."
sudo ip link add veth0 type veth peer name veth1

echo "📦 Назначаем интерфейсы в неймспейсы..."
sudo ip link set veth0 netns sender
sudo ip link set veth1 netns receiver

echo "🌐 Назначаем IP-адреса..."
sudo ip netns exec sender ip addr add 10.10.0.1/24 dev veth0
sudo ip netns exec receiver ip addr add 10.10.0.2/24 dev veth1

echo "🚀 Поднимаем интерфейсы..."
sudo ip netns exec sender ip link set veth0 up
sudo ip netns exec receiver ip link set veth1 up

echo "🔧 Создаём TAP-интерфейсы внутри неймспейсов..."
sudo ip netns exec sender ip tuntap add dev tap0 mode tap user $USER
sudo ip netns exec receiver ip tuntap add dev tap1 mode tap user $USER

sudo ip netns exec sender ip addr add 10.0.0.1/24 dev tap0
sudo ip netns exec receiver ip addr add 10.0.0.2/24 dev tap1

sudo ip netns exec sender ip link set tap0 up
sudo ip netns exec receiver ip link set tap1 up

echo "📌 Включаем маршрут и ICMP-обработку в receiver..."
sudo ip netns exec receiver ip route add 10.0.0.0/24 dev tap1 2>/dev/null || true
sudo ip netns exec receiver sysctl -w net.ipv4.icmp_echo_ignore_all=0 > /dev/null

echo "🧪 Запускаем приёмник (tap_decrypt)..."
sudo ip netns exec receiver ./build/tap_decrypt 10.10.0.2 5555 > /tmp/decrypt.log 2>&1 &
DECRYPT_PID=$!

sleep 1

echo "🧪 Запускаем отправитель (tap_encrypt)..."
sudo ip netns exec sender ./build/tap_encrypt 10.10.0.2 5555 > /tmp/encrypt.log 2>&1 &
ENCRYPT_PID=$!

sleep 2

echo "📡 Проверяем передачу кадра (ping через TAP)..."
if sudo ip netns exec sender ping -c 1 -I tap0 10.0.0.2 > /dev/null; then
    echo "✅ Ping прошёл успешно!"
    PING_OK=true
else
    echo "❌ Ping не прошёл"
    PING_OK=false
fi

echo "⏳ Ждём ещё 3 секунды на обмен..."
sleep 3

echo "🛑 Завершаем процессы..."
sudo kill $ENCRYPT_PID $DECRYPT_PID 2>/dev/null || true

echo "📄 Логи:"
echo "--- decrypt.log ---"
cat /tmp/decrypt.log
echo "--- encrypt.log ---"
cat /tmp/encrypt.log

echo "🧹 Удаляем всё..."
sudo ip netns del sender
sudo ip netns del receiver
sudo ip link delete veth0 || true

echo "🧪 Выполняем итоговую проверку..."

HASH_OK=false
if grep -q "✅ Хеши совпадают" /tmp/decrypt.log; then
    HASH_OK=true
fi

if [[ "$PING_OK" == "true" && "$HASH_OK" == "true" ]]; then
    echo "🎉 ✅ Тест пройден успешно: ping и шифрование работают корректно"
else
    echo "⚠️ ❌ Тест не пройден: возможны проблемы (ping или дешифровка)"
fi

echo "🏁 Тест завершён."

