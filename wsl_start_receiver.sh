#!/bin/bash
# ==============================================================
# LightCrypto - Автоматический запуск приёмника для WSL
# ==============================================================
# Использование: sudo ./wsl_start_receiver.sh [PORT] [TAP_IP]
# Пример: sudo ./wsl_start_receiver.sh 12346 10.0.0.2/24
# ==============================================================

set -e

# Параметры по умолчанию
PORT="${1:-12346}"
TAP_IP="${2:-10.0.0.2/24}"
TAP_DEV="tap1"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║   LightCrypto WSL - Запуск приёмника (decrypt)       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Требуются права root"
    echo "   Запустите: sudo $0"
    exit 1
fi

# Проверка бинарника
if [ ! -f "./build/tap_decrypt" ]; then
    echo "❌ Файл ./build/tap_decrypt не найден!"
    echo ""
    echo "Скомпилируйте проект:"
    echo "  g++ -o build/tap_decrypt src/tap_decrypt.cpp src/digital_codec.cpp -lsodium -pthread"
    exit 1
fi

# Создание TAP-интерфейса
echo "🔧 Создание TAP-интерфейса $TAP_DEV..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Удаляем старый интерфейс
if ip link show "$TAP_DEV" &>/dev/null; then
    echo "  → Удаление старого $TAP_DEV..."
    ip link delete "$TAP_DEV" 2>/dev/null || true
fi

# Создаём интерфейс
echo "  → Создание $TAP_DEV..."
ip tuntap add dev "$TAP_DEV" mode tap user "$SUDO_USER"

# Отключаем IPv6
echo "  → Отключение IPv6..."
sysctl -w net.ipv6.conf."$TAP_DEV".disable_ipv6=1 >/dev/null 2>&1

# Поднимаем интерфейс
echo "  → Активация интерфейса..."
ip link set "$TAP_DEV" up

# Назначаем IP
echo "  → Назначение IP: $TAP_IP..."
ip addr add "$TAP_IP" dev "$TAP_DEV" 2>/dev/null || echo "  ⚠️  IP уже назначен"

echo "✅ $TAP_DEV успешно настроен!"
echo ""

# Показываем статус
echo "📊 Статус $TAP_DEV:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ip addr show "$TAP_DEV"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Убиваем старые процессы
echo "🧹 Завершение старых процессов..."
pkill -9 tap_decrypt 2>/dev/null || true
sleep 1
echo ""

# Показываем информацию о WSL сети
echo "📡 Сетевая информация WSL:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
WSL_IP=$(hostname -I | awk '{print $1}')
echo "  WSL IP: $WSL_IP"
echo "  Порт прослушивания: $PORT"
echo "  TAP интерфейс: $TAP_DEV ($TAP_IP)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Напоминание
echo "⚠️  ВАЖНО ДЛЯ WSL:"
echo "   Если отправитель не может подключиться:"
echo "   1. Используйте WSL IP отправителя: $WSL_IP"
echo "   2. Или настройте UDP relay на Windows"
echo "   (см. WSL_SETUP_GUIDE.md)"
echo ""

# Запуск программы
echo "╔═══════════════════════════════════════════════════════╗"
echo "║           🚀 ЗАПУСК ПРИЁМНИКА (tap_decrypt)          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "⏳ Ожидание подключения отправителя..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Запускаем на всех интерфейсах (WSL-ready)
./build/tap_decrypt 0.0.0.0 "$PORT"

