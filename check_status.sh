#!/bin/bash

echo "=== Проверка состояния системы ==="
echo ""

echo "1. TAP интерфейсы:"
ip link show | grep -E "tap[0-9]|^[0-9]+:"
echo ""

echo "2. IP адреса TAP интерфейсов:"
ip addr show | grep -A 2 "tap[0-9]"
echo ""

echo "3. Запущенные процессы tap_encrypt/tap_decrypt:"
ps aux | grep -E "tap_(encrypt|decrypt)" | grep -v grep
echo ""

echo "4. Таблица маршрутизации:"
ip route | grep -E "10\.0\.0\."
echo ""

echo "5. Проверка доступности tap0:"
if ip link show tap0 >/dev/null 2>&1; then
    echo "✅ tap0 существует"
    ip link show tap0
else
    echo "❌ tap0 НЕ существует"
fi
echo ""

echo "6. ARP таблица:"
arp -n | grep -E "10\.0\.0\."
echo ""


