#!/bin/bash
# ==============================================================
# LightCrypto - Автоматический запуск отправителя для WSL
# ==============================================================
# Использование: sudo ./wsl_start_sender.sh <RECEIVER_IP> [PORT] [TAP_IP]
# Пример: sudo ./wsl_start_sender.sh 172.26.43.251 12346 10.0.0.1/24
# ==============================================================

set -e

# Проверка аргументов
if [ -z "$1" ]; then
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║   LightCrypto WSL - Запуск отправителя (encrypt)     ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    echo "❌ Использование: sudo $0 <IP_ПОЛУЧАТЕЛЯ> [ПОРТ] [TAP_IP]"
    echo ""
    echo "Примеры:"
    echo "  sudo $0 172.26.43.251"
    echo "  sudo $0 172.26.43.251 12346"
    echo "  sudo $0 172.26.43.251 12346 10.0.0.1/24"
    echo ""
    echo "💡 IP получателя:"
    echo "   - Используйте WSL IP устройства B (узнайте через: hostname -I)"
    echo "   - Если WSL IP недоступен, используйте Windows IP + UDP relay"
    echo ""
    exit 1
fi

# Параметры
RECEIVER_IP="$1"
PORT="${2:-12346}"
TAP_IP="${3:-10.0.0.1/24}"
TAP_DEV="tap0"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║   LightCrypto WSL - Запуск отправителя (encrypt)     ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Требуются права root"
    echo "   Запустите: sudo $0 $RECEIVER_IP"
    exit 1
fi

# Проверка бинарника
if [ ! -f "./build/tap_encrypt" ]; then
    echo "❌ Файл ./build/tap_encrypt не найден!"
    echo ""
    echo "Скомпилируйте проект:"
    echo "  g++ -o build/tap_encrypt src/tap_encrypt.cpp src/digital_codec.cpp -lsodium -pthread"
    exit 1
fi

# Проверка доступности получателя
echo "🔍 Проверка доступности получателя $RECEIVER_IP..."
if ping -c 1 -W 2 "$RECEIVER_IP" > /dev/null 2>&1; then
    echo "✅ Получатель $RECEIVER_IP доступен"
else
    echo "⚠️  Получатель $RECEIVER_IP не отвечает на ping"
    echo "   Продолжаем, но возможны проблемы с подключением..."
    echo ""
    echo "💡 Если подключение не работает:"
    echo "   1. Проверьте что tap_decrypt запущен на получателе"
    echo "   2. Проверьте брандмауэр Windows на получателе"
    echo "   3. Возможно нужен UDP relay (см. WSL_SETUP_GUIDE.md)"
fi
echo ""

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
pkill -9 tap_encrypt 2>/dev/null || true
sleep 1
echo ""

# Показываем информацию
echo "📡 Параметры подключения:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Получатель: $RECEIVER_IP:$PORT"
echo "  TAP интерфейс: $TAP_DEV ($TAP_IP)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Запуск программы
echo "╔═══════════════════════════════════════════════════════╗"
echo "║          🚀 ЗАПУСК ОТПРАВИТЕЛЯ (tap_encrypt)         ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "⏳ Установка зашифрованного канала..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Запускаем с новой WSL-оптимизацией
./build/tap_encrypt "$RECEIVER_IP" "$PORT"

