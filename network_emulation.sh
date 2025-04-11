#!/bin/bash
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

# TAP-интерфейсы и IP-адреса
TAP_A="tap0"
TAP_B="tap1"
TAP_A_IP="10.0.0.1"
TAP_B_IP="10.0.0.2"

# Порты
# A слушает на 6666 (B → A)
# B слушает на 5555 (A → B)
PORT_B2A="6666"  # tap_decrypt(A) слушает
PORT_A2B="5555"  # tap_decrypt(B) слушает

# Пути к бинарникам
ENCRYPT_BIN="./build/tap_encrypt"
DECRYPT_BIN="./build/tap_decrypt"

########################################
# 2. Подготовка окружения
########################################
echo "🧹 Удаляем старые неймспейсы..."
sudo ip netns del "$NS_A" 2>/dev/null || true
sudo ip netns del "$NS_B" 2>/dev/null || true
sudo ip link delete "$VETH_A" 2>/dev/null || true

echo "🔧 Создаём неймспейсы $NS_A и $NS_B..."
sudo ip netns add "$NS_A"
sudo ip netns add "$NS_B"

echo "🔗 Создаём veth: $VETH_A <-> $VETH_B"
sudo ip link add "$VETH_A" type veth peer name "$VETH_B"
sudo ip link set "$VETH_A" netns "$NS_A"
sudo ip link set "$VETH_B" netns "$NS_B"

echo "🌐 Настраиваем IP-адреса на veth..."
sudo ip netns exec "$NS_A" ip addr add "$IP_A/24" dev "$VETH_A"
sudo ip netns exec "$NS_B" ip addr add "$IP_B/24" dev "$VETH_B"
sudo ip netns exec "$NS_A" ip link set "$VETH_A" up
sudo ip netns exec "$NS_B" ip link set "$VETH_B" up

echo "🖧 Создаём TAP-интерфейсы $TAP_A / $TAP_B"
sudo ip netns exec "$NS_A" ip tuntap add dev "$TAP_A" mode tap user "$USER"
sudo ip netns exec "$NS_B" ip tuntap add dev "$TAP_B" mode tap user "$USER"

sudo ip netns exec "$NS_A" ip addr add "$TAP_A_IP/24" dev "$TAP_A"
sudo ip netns exec "$NS_B" ip addr add "$TAP_B_IP/24" dev "$TAP_B"
sudo ip netns exec "$NS_A" ip link set "$TAP_A" up
sudo ip netns exec "$NS_B" ip link set "$TAP_B" up

# Разрешаем ICMP-ответы
sudo ip netns exec "$NS_A" sysctl -w net.ipv4.icmp_echo_ignore_all=0 >/dev/null
sudo ip netns exec "$NS_B" sysctl -w net.ipv4.icmp_echo_ignore_all=0 >/dev/null

########################################
# 3. Запуск процессов в nsA
########################################
echo "🚀 Запускаем программы в $NS_A..."
sudo ip netns exec "$NS_A" bash -c "
  echo '[A] Запускаю tap_decrypt (слушает 0.0.0.0:$PORT_B2A)'
  $DECRYPT_BIN 0.0.0.0 $PORT_B2A > /tmp/decrypt_A.log 2>&1 &
  DECPID_A=\$!

  sleep 1

  echo '[A] Запускаю tap_encrypt (шлёт на $IP_B:$PORT_A2B)'
  $ENCRYPT_BIN $IP_B $PORT_A2B > /tmp/encrypt_A.log 2>&1 &
  ENCPID_A=\$!

  echo \$DECPID_A > /tmp/decA.pid
  echo \$ENCPID_A > /tmp/encA.pid
" &

########################################
# 4. Запуск процессов в nsB
########################################
echo "🚀 Запускаем программы в $NS_B..."
sudo ip netns exec "$NS_B" bash -c "
  echo '[B] Запускаю tap_decrypt (слушает 0.0.0.0:$PORT_A2B)'
  $DECRYPT_BIN 0.0.0.0 $PORT_A2B > /tmp/decrypt_B.log 2>&1 &
  DECPID_B=\$!

  sleep 1

  echo '[B] Запускаю tap_encrypt (шлёт на $IP_A:$PORT_B2A)'
  $ENCRYPT_BIN $IP_A $PORT_B2A > /tmp/encrypt_B.log 2>&1 &
  ENCPID_B=\$!

  echo \$DECPID_B > /tmp/decB.pid
  echo \$ENCPID_B > /tmp/encB.pid
" &
wait

echo "⏳ Небольшая пауза..."
sleep 2

########################################
# 5. Проверка ping
########################################
echo "📡 Пингуем из A (tap0) → B ($TAP_B_IP)"
if sudo ip netns exec "$NS_A" ping -c 1 -I "$TAP_A" "$TAP_B_IP"; then
  echo "✅ Ping A->B прошёл!"
  PING_AB=true
else
  echo "❌ Ping A->B не прошёл!"
  PING_AB=false
fi

echo "📡 Пингуем из B (tap1) → A ($TAP_A_IP)"
if sudo ip netns exec "$NS_B" ping -c 1 -I "$TAP_B" "$TAP_A_IP"; then
  echo "✅ Ping B->A прошёл!"
  PING_BA=true
else
  echo "❌ Ping B->A не прошёл!"
  PING_BA=false
fi

echo "⏳ Ждём ещё пару секунд..."
sleep 2

########################################
# 6. Останавливаем процессы
########################################
echo "🛑 Завершаем процессы..."

sudo ip netns exec "$NS_A" bash -c "
  kill \$(cat /tmp/decA.pid) 2>/dev/null || true
  kill \$(cat /tmp/encA.pid) 2>/dev/null || true
"

sudo ip netns exec "$NS_B" bash -c "
  kill \$(cat /tmp/decB.pid) 2>/dev/null || true
  kill \$(cat /tmp/encB.pid) 2>/dev/null || true
"

########################################
# 7. Логи
########################################
echo "---- ЛОГИ nsA decrypt ----"
sudo ip netns exec "$NS_A" cat /tmp/decrypt_A.log || true
echo "---- ЛОГИ nsA encrypt ----"
sudo ip netns exec "$NS_A" cat /tmp/encrypt_A.log || true

echo "---- ЛОГИ nsB decrypt ----"
sudo ip netns exec "$NS_B" cat /tmp/decrypt_B.log || true
echo "---- ЛОГИ nsB encrypt ----"
sudo ip netns exec "$NS_B" cat /tmp/encrypt_B.log || true

########################################
# 8. Проверка хешей
########################################
echo "🔎 Проверяем наличие 'Хеши совпадают' в логах..."
HASH_OK=false
if ( sudo ip netns exec "$NS_A" grep -q "✅ Хеши совпадают" /tmp/decrypt_A.log && \
     sudo ip netns exec "$NS_B" grep -q "✅ Хеши совпадают" /tmp/decrypt_B.log ); then
  HASH_OK=true
fi

########################################
# 9. Удаляем окружение
########################################
echo "🧹 Удаляем неймспейсы..."
sudo ip netns del "$NS_A"
sudo ip netns del "$NS_B"
sudo ip link delete "$VETH_A" 2>/dev/null || true

echo "📊 Результат:"
if [[ "$PING_AB" == "true" && "$PING_BA" == "true" && "$HASH_OK" == "true" ]]; then
  echo "🎉 Двунаправленный обмен (ICMP и шифрование) работает! A->B и B->A"
else
  echo "⚠️ Что-то не так, проверьте логи и конфигурацию!"
fi

exit 0



