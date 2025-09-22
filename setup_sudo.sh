#!/bin/bash
# Скрипт настройки sudo доступа для LightCrypto GUI

echo "🔐 Настройка sudo доступа для LightCrypto..."

# Получаем имя текущего пользователя
USERNAME=$(whoami)

# Получаем полный путь к текущей директории
CURRENT_DIR=$(pwd)

# Создаем правило sudoers для LightCrypto
SUDOERS_RULE="# LightCrypto GUI - доступ без пароля
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip netns exec ns1 $CURRENT_DIR/build/tap_encrypt*
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip netns exec ns2 $CURRENT_DIR/build/tap_decrypt*
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip netns exec *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip netns list
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip netns add *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip netns delete *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip link *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip addr *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip route *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip tuntap *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/killall tap_encrypt
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/killall tap_decrypt"

# Создаем временный файл
TEMP_FILE="/tmp/lightcrypto_sudoers"
echo "$SUDOERS_RULE" > "$TEMP_FILE"

echo "📋 Правила sudo для пользователя $USERNAME:"
echo "   - sudo ip netns exec ns1/ns2 $CURRENT_DIR/build/tap_encrypt/tap_decrypt"
echo "   - sudo ip netns (все операции с неймспейсами)"
echo "   - sudo killall tap_encrypt/tap_decrypt"
echo ""

# Проверяем синтаксис
if sudo visudo -c -f "$TEMP_FILE"; then
    echo "✅ Синтаксис правил корректен"
    
    # Копируем в sudoers.d
    sudo cp "$TEMP_FILE" "/etc/sudoers.d/lightcrypto"
    sudo chmod 440 "/etc/sudoers.d/lightcrypto"
    
    echo "✅ Правила sudo настроены успешно"
    echo "📋 Теперь следующие команды не требуют пароля:"
    echo "   - sudo ip netns exec ns1/ns2 ./build/tap_encrypt/tap_decrypt"
    echo "   - sudo ip netns (все операции с неймспейсами)"
    echo "   - sudo killall tap_encrypt/tap_decrypt"
    
else
    echo "❌ Ошибка в синтаксисе правил sudo"
    exit 1
fi

# Удаляем временный файл
rm -f "$TEMP_FILE"

echo ""
echo "🎯 Настройка завершена! Теперь можно запускать GUI без ввода пароля."
echo ""
echo "🚀 Для запуска GUI выполните:"
echo "   python3 encrypt_gui.py &"
echo "   python3 decrypt_gui.py"
