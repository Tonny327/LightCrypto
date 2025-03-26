#!/bin/bash

set -e

echo "🔧 Создание и настройка TAP-интерфейсов..."

# Удаляем старые, если остались
sudo ip link delete tap0 2>/dev/null || true
sudo ip link delete tap1 2>/dev/null || true

# Создаём интерфейсы
sudo ip tuntap add dev tap0 mode tap user $USER
sudo ip tuntap add dev tap1 mode tap user $USER

# Назначаем IP-адреса
sudo ip addr add 10.0.0.1/24 dev tap0
sudo ip addr add 10.0.0.2/24 dev tap1

# Поднимаем интерфейсы
sudo ip link set tap0 up
sudo ip link set tap1 up

# Добавляем маршрут (на всякий случай)
sudo ip route add 10.0.0.0/24 dev tap0 2>/dev/null || true

echo "✅ TAP-интерфейсы настроены:"
echo "    tap0 → 10.0.0.1"
echo "    tap1 → 10.0.0.2"
echo

