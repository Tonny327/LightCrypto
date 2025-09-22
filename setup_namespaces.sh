#!/bin/bash

# Скрипт для создания и настройки сетевых неймспейсов для тестирования LightCrypto
# Создает изолированные сетевые окружения ns1 и ns2 с TAP-интерфейсами и veth-парой

set -e  # Остановить выполнение при ошибке

echo "🧹 Очистка старых ресурсов..."
# Удаляем старые неймспейсы (игнорируем ошибки если их нет)
sudo ip netns delete ns1 2>/dev/null || true
sudo ip netns delete ns2 2>/dev/null || true

# Останавливаем процессы если они запущены
sudo killall tap_encrypt tap_decrypt tcpdump 2>/dev/null || true

echo "🔧 Создание неймспейсов ns1 и ns2..."
sudo ip netns add ns1
sudo ip netns add ns2

echo "📡 Создание TAP-интерфейсов..."
# Создаем TAP-интерфейс tap0 в ns1
sudo ip netns exec ns1 ip tuntap add dev tap0 mode tap
sudo ip netns exec ns1 ip addr add 10.0.0.1/24 dev tap0
sudo ip netns exec ns1 ip link set tap0 up

# Создаем TAP-интерфейс tap1 в ns2  
sudo ip netns exec ns2 ip tuntap add dev tap1 mode tap
sudo ip netns exec ns2 ip addr add 10.0.0.2/24 dev tap1
sudo ip netns exec ns2 ip link set tap1 up

echo "🔗 Создание veth-пары для связи между неймспейсами..."
# Создаем виртуальную Ethernet пару
sudo ip link add veth1 type veth peer name veth2

# Перемещаем концы пары в разные неймспейсы
sudo ip link set veth1 netns ns1
sudo ip link set veth2 netns ns2

# Назначаем IP-адреса veth-интерфейсам
sudo ip netns exec ns1 ip addr add 192.168.1.1/24 dev veth1
sudo ip netns exec ns1 ip link set veth1 up
sudo ip netns exec ns2 ip addr add 192.168.1.2/24 dev veth2
sudo ip netns exec ns2 ip link set veth2 up

echo "🌐 Настройка маршрутизации..."
# Добавляем маршруты по умолчанию
sudo ip netns exec ns1 ip route add default via 192.168.1.2
sudo ip netns exec ns2 ip route add default via 192.168.1.1

echo "🚫 Отключение IPv6..."
# Отключаем IPv6 для упрощения тестирования
sudo ip netns exec ns1 sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null
sudo ip netns exec ns2 sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null

echo "✅ Настройка завершена!"
echo ""
echo "📋 Созданная конфигурация:"
echo "  Неймспейс ns1:"
echo "    - TAP-интерфейс tap0: 10.0.0.1/24"
echo "    - veth-интерфейс veth1: 192.168.1.1/24"
echo ""
echo "  Неймспейс ns2:"
echo "    - TAP-интерфейс tap1: 10.0.0.2/24" 
echo "    - veth-интерфейс veth2: 192.168.1.2/24"
echo ""
echo "🚀 СПОСОБЫ ТЕСТИРОВАНИЯ:"
echo ""
echo "📡 1. БАЗОВОЕ ТЕСТИРОВАНИЕ ШИФРОВАНИЯ КАДРОВ:"
echo "  Терминал 1 (приемник в ns2):"
echo "    sudo ip netns exec ns2 ./build/tap_decrypt 192.168.1.2 12345"
echo ""
echo "  Терминал 2 (отправитель в ns1):"
echo "    sudo ip netns exec ns1 ./build/tap_encrypt 192.168.1.2 12345"
echo ""
echo "  Терминал 3 (генерация трафика ping):"
echo "    sudo ip netns exec ns1 ping 10.0.0.2"
echo ""
echo "💬 2. ТЕСТИРОВАНИЕ РЕЖИМА СООБЩЕНИЙ:"
echo "  Терминал 1 (приемник сообщений в ns2):"
echo "    sudo ip netns exec ns2 ./build/tap_decrypt --msg 192.168.1.2 12345"
echo ""
echo "  Терминал 2 (отправитель сообщений в ns1):"
echo "    sudo ip netns exec ns1 ./build/tap_encrypt --msg 192.168.1.2 12345"
echo "    # Затем вводите текст для отправки"
echo ""
echo "🔥 3. НАГРУЗОЧНОЕ ТЕСТИРОВАНИЕ С IPERF:"
echo "  TCP тест:"
echo "    # Терминал 3 - TCP сервер в ns2:"
echo "    sudo ip netns exec ns2 iperf -s -B 10.0.0.2"
echo "    # Терминал 4 - TCP клиент в ns1:"
echo "    sudo ip netns exec ns1 iperf -c 10.0.0.2 -t 10"
echo ""
echo "  UDP тест:"
echo "    # Терминал 3 - UDP сервер в ns2:"
echo "    sudo ip netns exec ns2 iperf -s -u -B 10.0.0.2"
echo "    # Терминал 4 - UDP клиент в ns1:"
echo "    sudo ip netns exec ns1 iperf -c 10.0.0.2 -u -t 10 -b 100M"
echo ""
echo "🧨 4. ТЕСТИРОВАНИЕ С HPING3:"
echo "  TCP SYN пакеты:"
echo "    sudo ip netns exec ns1 hping3 10.0.0.2 -S -p 80 -c 10"
echo ""
echo "  UDP пакеты:"
echo "    sudo ip netns exec ns1 hping3 10.0.0.2 -2 -p 5000 -c 10"
echo ""
echo "📊 5. МОНИТОРИНГ ТРАФИКА:"
echo "  Захват на tap0 (ns1):"
echo "    sudo ip netns exec ns1 tcpdump -i tap0 -v"
echo ""
echo "  Захват на tap1 (ns2):"
echo "    sudo ip netns exec ns2 tcpdump -i tap1 -v"
echo ""
echo "  Захват UDP трафика между неймспейсами:"
echo "    sudo ip netns exec ns1 tcpdump -i veth1 udp -v"
echo ""
echo "⚡ 6. ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ШИФРОВАНИЯ:"
echo "  Запуск теста скорости (без сети):"
echo "    ./build/lightcrypto"
echo ""
echo "🔍 7. ПРОВЕРКА СВЯЗНОСТИ:"
echo "  Ping через TAP:"
echo "    sudo ip netns exec ns1 ping 10.0.0.2"
echo "    sudo ip netns exec ns2 ping 10.0.0.1"
echo ""
echo "  Ping через veth (прямая связь):"
echo "    sudo ip netns exec ns1 ping 192.168.1.2"
echo "    sudo ip netns exec ns2 ping 192.168.1.1"
echo ""
echo "🎯 8. КОМПЛЕКСНОЕ АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ:"
echo "  Запуск полного тестового сценария:"
echo "    ./network_emulation.sh"
echo ""
echo "🧹 ОЧИСТКА РЕСУРСОВ:"
echo "  Удаление неймспейсов:"
echo "    sudo ip netns delete ns1 ns2"
echo ""
echo "  Остановка всех процессов:"
echo "    sudo killall tap_encrypt tap_decrypt tcpdump iperf hping3 2>/dev/null || true"
echo ""
echo "💡 ПОЛЕЗНЫЕ КОМАНДЫ:"
echo "  Список неймспейсов:"
echo "    sudo ip netns list"
echo ""
echo "  Вход в неймспейс для отладки:"
echo "    sudo ip netns exec ns1 bash"
echo "    sudo ip netns exec ns2 bash"
echo ""
echo "  Просмотр интерфейсов в неймспейсе:"
echo "    sudo ip netns exec ns1 ip addr show"
echo "    sudo ip netns exec ns2 ip addr show"
