#!/bin/bash
#
# network_emulation_fixed.sh
#
# Переписанный скрипт для тестирования bidirectional Li-Fi шифрования
# с учётом рекомендаций:
# 1) Отдельные порты для netcat-тестов
# 2) Длительное время работы процессов tap_decrypt / tap_encrypt
# 3) Проверка ping по br0
# 4) Возможность вручную пустить реальный трафик через tap0/tap1

set -e

########################################
# 1. Параметры
########################################
NS_A="nodeA"
NS_B="nodeB"

# veth-имена и IP
VETH_A="vethA"
VETH_B="vethB"
IP_A="10.10.0.1"
IP_B="10.10.0.2"

# TAP-интерфейсы и IP-адреса на бридже
TAP_A="tap0"
TAP_B="tap1"
TAP_A_IP="10.0.0.1"
TAP_B_IP="10.0.0.2"

# Порты «боевые», которые занимают tap_decrypt
PORT_B2A="6666"  # tap_decrypt(A) слушает
PORT_A2B="5555"  # tap_decrypt(B) слушает

# Порты для проверки через netcat (другие, чтоб не конфликтовать)
TEST_PORT_A2B="5557"
TEST_PORT_B2A="6667"

# Пути к бинарникам
ENCRYPT_BIN="./build/tap_encrypt"
DECRYPT_BIN="./build/tap_decrypt"

########################################
# 2. Проверка бинарников
########################################
if [[ ! -x "$ENCRYPT_BIN" || ! -x "$DECRYPT_BIN" ]]; then
    echo "❌ Бинарники не найдены или не исполняемы: $ENCRYPT_BIN, $DECRYPT_BIN"
    exit 1
fi

########################################
# 3. Подготовка окружения
########################################
echo "🧹 Удаляем старые неймспейсы/интерфейсы..."
sudo ip netns del "$NS_A" 2>/dev/null || true
sudo ip netns del "$NS_B" 2>/dev/null || true
sudo ip link delete "$VETH_A" 2>/dev/null || true

echo "🔧 Создаём неймспейсы $NS_A и $NS_B..."
sudo ip netns add "$NS_A"
sudo ip netns add "$NS_B"

echo "🔗 Создаём veth: $VETH_A <-> $VETH_B"
sudo ip link add "$VETH_A" type veth peer name "$VETH_B"

# Помещаем концы в разные неймспейсы
sudo ip link set "$VETH_A" netns "$NS_A"
sudo ip link set "$VETH_B" netns "$NS_B"

# Назначаем IP
echo "🌐 Настраиваем IP-адреса на veth..."
sudo ip netns exec "$NS_A" ip addr add "$IP_A/24" dev "$VETH_A"
sudo ip netns exec "$NS_B" ip addr add "$IP_B/24" dev "$VETH_B"
sudo ip netns exec "$NS_A" ip link set "$VETH_A" up
sudo ip netns exec "$NS_B" ip link set "$VETH_B" up

echo "🖧 Создаём TAP-интерфейсы $TAP_A / $TAP_B"
sudo ip netns exec "$NS_A" ip tuntap add dev "$TAP_A" mode tap user "$USER"
sudo ip netns exec "$NS_B" ip tuntap add dev "$TAP_B" mode tap user "$USER"
sudo ip netns exec "$NS_A" ip link set "$TAP_A" up
sudo ip netns exec "$NS_B" ip link set "$TAP_B" up

echo "🌉 Настраиваем мосты br0 в каждом неймспейсе..."
sudo ip netns exec "$NS_A" ip link add name br0 type bridge
sudo ip netns exec "$NS_A" ip link set "$TAP_A" master br0
sudo ip netns exec "$NS_A" ip link set "$VETH_A" master br0
sudo ip netns exec "$NS_A" ip link set br0 up
sudo ip netns exec "$NS_A" ip addr add "$TAP_A_IP/24" dev br0
sudo ip netns exec "$NS_A" ip addr flush dev "$TAP_A"

sudo ip netns exec "$NS_B" ip link add name br0 type bridge
sudo ip netns exec "$NS_B" ip link set "$TAP_B" master br0
sudo ip netns exec "$NS_B" ip link set "$VETH_B" master br0
sudo ip netns exec "$NS_B" ip link set br0 up
sudo ip netns exec "$NS_B" ip addr add "$TAP_B_IP/24" dev br0
sudo ip netns exec "$NS_B" ip addr flush dev "$TAP_B"

# Разрешаем forwarding, icmp, udp
sudo ip netns exec "$NS_A" sysctl -w net.ipv4.ip_forward=1 >/dev/null
sudo ip netns exec "$NS_B" sysctl -w net.ipv4.ip_forward=1 >/dev/null
sudo ip netns exec "$NS_A" iptables -F
sudo ip netns exec "$NS_B" iptables -F
sudo ip netns exec "$NS_A" iptables -A INPUT -p udp -j ACCEPT
sudo ip netns exec "$NS_B" iptables -A INPUT -p udp -j ACCEPT
sudo ip netns exec "$NS_A" iptables -A INPUT -p icmp -j ACCEPT
sudo ip netns exec "$NS_B" iptables -A INPUT -p icmp -j ACCEPT
sudo ip netns exec "$NS_A" iptables -A FORWARD -p udp -j ACCEPT
sudo ip netns exec "$NS_B" iptables -A FORWARD -p udp -j ACCEPT

########################################
# 4. Запуск наших программ
########################################
echo "🚀 Запускаем процессы в $NS_A..."
sudo ip netns exec "$NS_A" bash -c "
  echo '[A] Запускаю tap_decrypt на 0.0.0.0:$PORT_B2A'
  $DECRYPT_BIN 0.0.0.0 $PORT_B2A > /tmp/decrypt_A.log 2>&1 &
  DECPID_A=\$!
  sleep 2
  echo '[A] Запускаю tap_encrypt на $IP_B:$PORT_A2B'
  $ENCRYPT_BIN $IP_B $PORT_A2B > /tmp/encrypt_A.log 2>&1 &
  ENCPID_A=\$!
  echo \$DECPID_A > /tmp/decA.pid
  echo \$ENCPID_A > /tmp/encA.pid
"

echo "🚀 Запускаем процессы в $NS_B..."
sudo ip netns exec "$NS_B" bash -c "
  echo '[B] Запускаю tap_decrypt на 0.0.0.0:$PORT_A2B'
  $DECRYPT_BIN 0.0.0.0 $PORT_A2B > /tmp/decrypt_B.log 2>&1 &
  DECPID_B=\$!
  sleep 2
  echo '[B] Запускаю tap_encrypt на $IP_A:$PORT_B2A'
  $ENCRYPT_BIN $IP_A $PORT_B2A > /tmp/encrypt_B.log 2>&1 &
  ENCPID_B=\$!
  echo \$DECPID_B > /tmp/decB.pid
  echo \$ENCPID_B > /tmp/encB.pid
"

echo "⏳ Даем время на инициализацию..."
sleep 5

########################################
# 5. Проверка UDP-связности netcat'ом (на других портах)
########################################
echo "🔍 Проверяем UDP-связность A→B (порт $TEST_PORT_A2B)..."
sudo ip netns exec "$NS_B" nc -u -l "$TEST_PORT_A2B" > /tmp/udp_test_B.log 2>/tmp/udp_test_B_err.log &
NCPID_B=$!
sleep 1
echo "hello from A" | sudo ip netns exec "$NS_A" nc -u -w 1 "$IP_B" "$TEST_PORT_A2B" 2>/tmp/udp_test_A_err.log
sleep 1
sudo kill $NCPID_B 2>/dev/null || true
if grep -q "hello from A" /tmp/udp_test_B.log; then
    echo "✅ UDP A→B работает (через порт $TEST_PORT_A2B)"
else
    echo "❌ UDP A→B не работает (через порт $TEST_PORT_A2B)"
    echo "Лог ошибок A: $(cat /tmp/udp_test_A_err.log)"
    echo "Лог ошибок B: $(cat /tmp/udp_test_B_err.log)"
fi

echo "🔍 Проверяем UDP-связность B→A (порт $TEST_PORT_B2A)..."
sudo ip netns exec "$NS_A" nc -u -l "$TEST_PORT_B2A" > /tmp/udp_test_A.log 2>/tmp/udp_test_A_err.log &
NCPID_A=$!
sleep 1
echo "hello from B" | sudo ip netns exec "$NS_B" nc -u -w 1 "$IP_A" "$TEST_PORT_B2A" 2>/tmp/udp_test_B_err.log
sleep 1
sudo kill $NCPID_A 2>/dev/null || true
if grep -q "hello from B" /tmp/udp_test_A.log; then
    echo "✅ UDP B→A работает (через порт $TEST_PORT_B2A)"
else
    echo "❌ UDP B→A не работает (через порт $TEST_PORT_B2A)"
    echo "Лог ошибок B: $(cat /tmp/udp_test_B_err.log)"
    echo "Лог ошибок A: $(cat /tmp/udp_test_A_err.log)"
fi

########################################
# 6. Проверка ping по br0
########################################
echo "📡 Пингуем из A (br0) → B ($TAP_B_IP)..."
if sudo ip netns exec "$NS_A" ping -c 1 -I br0 "$TAP_B_IP"; then
  echo "✅ Ping A->B прошёл!"
  PING_AB=true
else
  echo "❌ Ping A->B не прошёл"
fi

echo "📡 Пингуем из B (br0) → A ($TAP_A_IP)..."
if sudo ip netns exec "$NS_B" ping -c 1 -I br0 "$TAP_A_IP"; then
  echo "✅ Ping B->A прошёл!"
  PING_BA=true
else
  echo "❌ Ping B->A не прошёл"
fi

########################################
# 7. (Опционально) Проверка трафика через tap-интерфейсы
#    Можете здесь вручную послать кадр или использовать tcpdump
#    для генерации трафика, тогда появятся логи "Зашифрован кадр..."
########################################

echo "🔎 Сейчас процессы tap_encrypt/decrypt работают."
echo "Вы можете в одном терминале зайти в nsA (ip netns exec nodeA bash)"
echo "и в другом nsB (ip netns exec nodeB bash), сгенерировать трафик на tap0/tap1."
echo "Например, можно запустить 'tcpdump -i tap0' и 'tcpdump -i tap1', пингануть 10.0.0.2 и т.д."
echo "Либо отправить сообщения с помощью tap_encrypt --msg."

########################################
# 8. Делаем паузу, чтобы дать время на тест
########################################
echo "⏸ Оставим процессы работать 30 секунд, можно понаблюдать логи..."
sleep 30

########################################
# 9. Завершаем процессы и выводим логи
########################################
echo "🛑 Останавливаем tap_decrypt / tap_encrypt..."
sudo ip netns exec "$NS_A" bash -c "
  kill \$(cat /tmp/decA.pid) 2>/dev/null || true
  kill \$(cat /tmp/encA.pid) 2>/dev/null || true
"
sudo ip netns exec "$NS_B" bash -c "
  kill \$(cat /tmp/decB.pid) 2>/dev/null || true
  kill \$(cat /tmp/encB.pid) 2>/dev/null || true
"

echo "---- ЛОГИ nsA decrypt ----"
sudo ip netns exec "$NS_A" cat /tmp/decrypt_A.log || true
echo "---- ЛОГИ nsA encrypt ----"
sudo ip netns exec "$NS_A" cat /tmp/encrypt_A.log || true
echo "---- ЛОГИ nsB decrypt ----"
sudo ip netns exec "$NS_B" cat /tmp/decrypt_B.log || true
echo "---- ЛОГИ nsB encrypt ----"
sudo ip netns exec "$NS_B" cat /tmp/encrypt_B.log || true

########################################
# 10. Проверка «Хеши совпадают» в логах
########################################
echo "🔎 Ищем 'Хеши совпадают' в логах..."
HASH_OK=false
if ( sudo ip netns exec "$NS_A" grep -q "Хеши совпадают" /tmp/decrypt_A.log && \
     sudo ip netns exec "$NS_B" grep -q "Хеши совпадают" /tmp/decrypt_B.log ); then
  HASH_OK=true
fi

########################################
# 11. Удаляем окружение
########################################
echo "🧹 Удаляем неймспейсы..."
sudo ip netns del "$NS_A" 2>/dev/null || true
sudo ip netns del "$NS_B" 2>/dev/null || true
sudo ip link delete "$VETH_A" 2>/dev/null || true

########################################
# 12. Итог
########################################
if [[ "$PING_AB" == "true" && "$PING_BA" == "true" && "$HASH_OK" == "true" ]]; then
  echo "🎉 Двунаправленный обмен (ICMP и шифрование) проверен: A->B и B->A!"
else
  echo "⚠️ Проверка завершена, возможно не все условия выполнены."
  echo "   Посмотрите логи и убедитесь, что трафик реально шёл через tap."
fi

exit 0
