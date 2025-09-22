#!/bin/bash

# 🧹 Простой скрипт очистки TAP интерфейсов и неймспейсов

echo "🧹 Очистка неймспейсов и TAP интерфейсов"
echo "======================================="

# Проверяем права root
if [[ $EUID -ne 0 ]]; then
    echo "Запуск с sudo..."
    exec sudo "$0" "$@"
fi

echo "🔍 Поиск и завершение процессов LightCrypto..."

# Завершаем все процессы tap_encrypt и tap_decrypt
for process in tap_encrypt tap_decrypt; do
    pids=$(pgrep -f "$process" 2>/dev/null)
    if [[ -n "$pids" ]]; then
        echo "🛑 Завершаем процессы $process: $pids"
        kill -TERM $pids 2>/dev/null
        sleep 2
        # Принудительное завершение если не помогло
        kill -KILL $pids 2>/dev/null
    else
        echo "✅ Процессы $process не найдены"
    fi
done

echo ""
echo "🔍 Очистка TAP интерфейсов..."

# Удаляем TAP интерфейсы из неймспейсов
for ns in ns1 ns2; do
    if ip netns list | grep -q "^$ns"; then
        echo "🗑️  Очистка интерфейсов в неймспейсе $ns..."
        
        # Получаем список всех интерфейсов в неймспейсе
        interfaces=$(ip netns exec $ns ip link show 2>/dev/null | grep -E '^[0-9]+:' | awk -F': ' '{print $2}' | awk '{print $1}')
        
        for iface in $interfaces; do
            if [[ "$iface" != "lo" ]]; then
                echo "  - Удаляем интерфейс $iface из $ns"
                ip netns exec $ns ip link set $iface down 2>/dev/null
                ip netns exec $ns ip link delete $iface 2>/dev/null
            fi
        done
    fi
done

echo ""
echo "🗑️  Удаление неймспейсов..."

# Удаляем неймспейсы
for ns in ns1 ns2; do
    if ip netns list | grep -q "^$ns"; then
        echo "  - Удаляем неймспейс $ns"
        ip netns delete $ns 2>/dev/null
        if [[ $? -eq 0 ]]; then
            echo "    ✅ $ns удален"
        else
            echo "    ❌ Ошибка удаления $ns"
        fi
    else
        echo "  ✅ Неймспейс $ns не существует"
    fi
done

echo ""
echo "🔍 Очистка глобальных TAP интерфейсов..."

# Удаляем TAP интерфейсы в основном неймспейсе
for iface in tap0 tap1; do
    if ip link show $iface &>/dev/null; then
        echo "  - Удаляем глобальный интерфейс $iface"
        ip link set $iface down 2>/dev/null
        ip link delete $iface 2>/dev/null
        if [[ $? -eq 0 ]]; then
            echo "    ✅ $iface удален"
        else
            echo "    ❌ Ошибка удаления $iface"
        fi
    else
        echo "  ✅ Интерфейс $iface не существует"
    fi
done

echo ""
echo "🔍 Очистка veth пар..."

# Удаляем veth интерфейсы
for iface in veth1 veth2; do
    if ip link show $iface &>/dev/null; then
        echo "  - Удаляем veth интерфейс $iface"
        ip link set $iface down 2>/dev/null
        ip link delete $iface 2>/dev/null
        if [[ $? -eq 0 ]]; then
            echo "    ✅ $iface удален"
        else
            echo "    ❌ Ошибка удаления $iface"
        fi
    else
        echo "  ✅ Интерфейс $iface не существует"
    fi
done

echo ""
echo "🔍 Очистка остаточных TUN/TAP интерфейсов..."

# Поиск и удаление всех TUN/TAP интерфейсов
tun_interfaces=$(ip link show type tun 2>/dev/null | grep -E '^[0-9]+:' | awk -F': ' '{print $2}' | awk '{print $1}')
tap_interfaces=$(ip link show type tap 2>/dev/null | grep -E '^[0-9]+:' | awk -F': ' '{print $2}' | awk '{print $1}')

for iface in $tun_interfaces $tap_interfaces; do
    if [[ "$iface" =~ ^(tap|tun) ]]; then
        echo "  - Найден остаточный интерфейс $iface, удаляем..."
        ip link set $iface down 2>/dev/null
        ip link delete $iface 2>/dev/null
    fi
done

echo ""
echo "🧹 Очистка модулей ядра..."

# Выгружаем модули TUN/TAP если они не используются
if ! lsmod | grep -q tun; then
    echo "  ✅ Модуль tun не загружен"
else
    echo "  ℹ️  Модуль tun используется другими процессами"
fi

echo ""
echo "🔍 Финальная проверка..."

# Проверяем результат
echo "📊 Состояние системы после очистки:"
echo ""

echo "Неймспейсы:"
ns_list=$(ip netns list 2>/dev/null)
if [[ -z "$ns_list" ]]; then
    echo "  ✅ Неймспейсы отсутствуют"
else
    echo "  ⚠️  Остались неймспейсы:"
    echo "$ns_list" | sed 's/^/    /'
fi

echo ""
echo "TUN/TAP интерфейсы:"
tun_tap_list=$(ip link show type tun 2>/dev/null; ip link show type tap 2>/dev/null)
if [[ -z "$tun_tap_list" ]]; then
    echo "  ✅ TUN/TAP интерфейсы отсутствуют"
else
    echo "  ⚠️  Остались TUN/TAP интерфейсы:"
    echo "$tun_tap_list" | sed 's/^/    /'
fi

echo ""
echo "Процессы LightCrypto:"
lightcrypto_processes=$(pgrep -f 'tap_(encrypt|decrypt)' 2>/dev/null)
if [[ -z "$lightcrypto_processes" ]]; then
    echo "  ✅ Процессы LightCrypto отсутствуют"
else
    echo "  ⚠️  Остались процессы:"
    ps aux | grep -E 'tap_(encrypt|decrypt)' | grep -v grep | sed 's/^/    /'
fi

echo ""
echo "✅ Очистка завершена!"
