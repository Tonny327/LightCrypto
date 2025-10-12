#include <iostream>
#include <vector>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/if_tun.h>
#include <netinet/in.h>
#include <net/if.h>
#include <sys/socket.h>
#include <sodium.h>
#include <arpa/inet.h> // для inet_pton
#include <thread>
#include "digital_codec.h"


constexpr size_t MAX_PACKET_SIZE = 2000;
constexpr size_t KEY_SIZE = crypto_aead_chacha20poly1305_IETF_KEYBYTES;
constexpr size_t NONCE_SIZE = crypto_aead_chacha20poly1305_IETF_NPUBBYTES;
constexpr size_t HASH_SIZE = crypto_hash_sha256_BYTES;

int open_tap(const std::string &dev_name)
{
    struct ifreq ifr{};
    int fd = open("/dev/net/tun", O_RDWR);
    if (fd < 0)
    {
        perror("open /dev/net/tun");
        exit(1);
    }

    ifr.ifr_flags = IFF_TAP | IFF_NO_PI;
    std::strncpy(ifr.ifr_name, dev_name.c_str(), IFNAMSIZ);

    if (ioctl(fd, TUNSETIFF, &ifr) < 0)
    {
        perror("ioctl TUSETIFF");
        close(fd);
        exit(1);
    }

    return fd;
}

void receive_frames(int tap_fd, int sock, const std::vector<unsigned char> &key)
{
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        ssize_t nrecv = recv(sock, buffer, sizeof(buffer), 0);
        if (nrecv <= NONCE_SIZE)
            continue;

        std::vector<unsigned char> nonce(buffer, buffer + NONCE_SIZE);
        std::vector<unsigned char> ciphertext(buffer + NONCE_SIZE, buffer + nrecv);

        std::vector<unsigned char> decrypted(ciphertext.size());
        unsigned long long decrypted_len = 0;

        int result = crypto_aead_chacha20poly1305_ietf_decrypt(
            decrypted.data(), &decrypted_len,
            nullptr,
            ciphertext.data(), ciphertext.size(),
            nullptr, 0,
            nonce.data(), key.data());

        if (result != 0)
        {
            std::cerr << "❌ Ошибка расшифровки в receive_frames!\n";
            continue;
        }

        if (decrypted_len < HASH_SIZE)
        {
            std::cerr << "❌ Слишком маленький расшифрованный буфер!\n";
            continue;
        }

        unsigned char received_hash[HASH_SIZE];
        std::memcpy(received_hash, decrypted.data(), HASH_SIZE);

        size_t msg_len = decrypted_len - HASH_SIZE;

        unsigned char actual_hash[HASH_SIZE];
        crypto_hash_sha256(actual_hash, decrypted.data() + HASH_SIZE, msg_len);

        bool hash_valid = (std::memcmp(received_hash, actual_hash, HASH_SIZE) == 0);
        if (!hash_valid)
        {
            std::cerr << "⚠️  Хеш не совпадает в receive_frames — данные могут быть повреждены!\n";
            std::cerr << "⚠️  Записываем данные для отладки (возможно искажены)\n";
        }

        size_t data_len = decrypted_len - HASH_SIZE;
        std::vector<unsigned char> data_buf(data_len);
        std::memcpy(data_buf.data(), decrypted.data() + HASH_SIZE, data_len);

        write(tap_fd, data_buf.data(), data_len);
        std::cout << "✅ Принят и расшифрован кадр из tap1 (" << data_len << " байт)\n";
    }
}

void receive_frames_codec(int tap_fd, int sock, digitalcodec::DigitalCodec *codec)
{
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        ssize_t nrecv = recv(sock, buffer, sizeof(buffer), 0);
        if (nrecv <= 0)
            continue;

        std::vector<uint8_t> framed(buffer, buffer + nrecv);
        std::vector<uint8_t> decoded_bytes = codec->decodeMessage(framed, 0);
        if (decoded_bytes.empty())
        {
            std::cerr << "❌ Критическая ошибка декодирования кадра (буфер пуст)!\n";
            continue;
        }
        write(tap_fd, decoded_bytes.data(), decoded_bytes.size());
        std::cout << "✅ Принят и раскодирован кадр из tap1 (" << decoded_bytes.size() << " байт)\n";
    }
}

int main(int argc, char *argv[])
{
    bool message_mode = false;
    // Optional codec parameters
    bool use_codec = false;
    std::string codec_csv;
    digitalcodec::CodecParams codec_params; // defaults: M=8, Q=4, fun=1, h1=7,h2=23

    // Parse flags (order-agnostic). Collect positional args for IP/port afterwards
    std::vector<std::string> positionals;
    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        if (arg == "--msg") { message_mode = true; continue; }
        if (arg == "--codec" && i + 1 < argc) { use_codec = true; codec_csv = argv[++i]; continue; }
        if (arg == "--M" && i + 1 < argc) { codec_params.bitsM = std::stoi(argv[++i]); continue; }
        if (arg == "--Q" && i + 1 < argc) { codec_params.bitsQ = std::stoi(argv[++i]); continue; }
        if (arg == "--fun" && i + 1 < argc) { codec_params.funType = std::stoi(argv[++i]); continue; }
        if (arg == "--h1" && i + 1 < argc) { codec_params.h1 = std::stoi(argv[++i]); continue; }
        if (arg == "--h2" && i + 1 < argc) { codec_params.h2 = std::stoi(argv[++i]); continue; }
        positionals.push_back(arg);
    }

    if (sodium_init() < 0)
    {
        std::cerr << "Не удалось инициализировать libsodium\n";
        return 1;
    }
    const char *ip_str = "127.0.0.1";
    int port = 12345;
    if (positionals.size() >= 1) ip_str = positionals[0].c_str();
    if (positionals.size() >= 2) port = std::stoi(positionals[1]);

    std::cout << "🌐 Используем IP: " << ip_str << ", порт: " << port << "\n";

    std::string ping_cmd = "ping -c 1 " + std::string(ip_str) + " > /dev/null 2>&1";
    int ping_result = system(ping_cmd.c_str());

    if (ping_result != 0)
    {
        std::cout << "⚠️  Внимание: IP-адрес " << ip_str
                  << " недоступен (ping не прошёл), но продолжаем...\n";
    }
    else
    {
        std::cout << "✅ IP-адрес " << ip_str << " доступен, начинаем работу...\n";
    }
    // if (ping_result != 0)
    // {
    //     std::cout << "⚠️  Внимание: IP-адрес " << ip_str << " недоступен (ping не прошёл)\n";
    //     std::cout << "Продолжить отправку данных? [y/N]: ";

    //     std::string answer;
    //     std::getline(std::cin, answer);
    //     if (answer != "y" && answer != "Y")
    //     {
    //         std::cout << "🚫 Отправка отменена пользователем.\n";
    //         return 1;
    //     }
    // }
    // else
    // {
    //     std::cout << "✅ IP-адрес " << ip_str << " доступен, начинаем работу...\n";
    // }

    // Открываем tap0
    int tap_fd = open_tap("tap0");
    std::cout << "📡 tap0 открыт для чтения Ethernet-кадров\n";

    // Создаём UDP-сокет
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
    {
        perror("socket");
        return 1;
    }

    // Формируем адрес назначения
    sockaddr_in dest_addr{};
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(port);
    if (inet_pton(AF_INET, ip_str, &dest_addr.sin_addr) <= 0)
    {
        std::cerr << "❌ Неверный IP-адрес\n";
        return 1;
    }

    // Объявляем ключи для всех режимов
    std::vector<unsigned char> rx_key(KEY_SIZE);
    std::vector<unsigned char> tx_key(KEY_SIZE);
    std::thread receive_thread;

    if (use_codec)
    {
        // РЕЖИМ КОДЕКА: обмен ключами не нужен, только Matlab-шифрование
        std::cout << "🎛️  Режим цифрового кодека — обмен ключами не требуется\n";
    }
    else
    {
        // СТАРЫЙ РЕЖИМ: обмен ключами libsodium
        // === [Автоматический обмен ключами через UDP] ===
        unsigned char my_public_key[crypto_kx_PUBLICKEYBYTES];
        unsigned char my_private_key[crypto_kx_SECRETKEYBYTES];
        crypto_kx_keypair(my_public_key, my_private_key);

        // 1. Отправляем свой публичный ключ получателю
        sendto(sock, my_public_key, crypto_kx_PUBLICKEYBYTES, 0,
               (sockaddr *)&dest_addr, sizeof(dest_addr));
        std::cout << "📤 Публичный ключ отправлен получателю\n";

        // 2. Принимаем публичный ключ от получателя
        unsigned char receiver_public_key[crypto_kx_PUBLICKEYBYTES];
        ssize_t received = recv(sock, receiver_public_key, crypto_kx_PUBLICKEYBYTES, 0);
        if (received != crypto_kx_PUBLICKEYBYTES)
        {
            std::cerr << "❌ Ошибка при получении публичного ключа получателя\n";
            return 1;
        }
        std::cout << "📥 Публичный ключ получен от получателя\n";

        // 3. Вычисляем ключи (rx/tx)
        if (crypto_kx_client_session_keys(rx_key.data(), tx_key.data(),
                                          my_public_key, my_private_key,
                                          receiver_public_key) != 0)
        {
            std::cerr << "❌ Ошибка при расчёте общего ключа (client)\n";
            return 1;
        }

        // Запускаем приём кадров в отдельном потоке ТОЛЬКО если НЕ режим сообщений
        if (!message_mode)
        {
            receive_thread = std::thread(receive_frames, tap_fd, sock, std::ref(rx_key));
            std::cout << "🔄 Двунаправленная передача включена\n";
        }
    }

    // Вектор для nonce (уникальный для каждого кадра)
    std::vector<unsigned char> nonce(NONCE_SIZE);

    // Initialize optional codec
    digitalcodec::DigitalCodec codec;
    if (use_codec)
    {
        try {
            codec.configure(codec_params);
            if (codec_csv.empty()) {
                std::cerr << "❌ Не указан путь к CSV для --codec. Укажите файл через --codec <path>.\n";
                return 1;
            }
            codec.loadCoefficientsCSV(codec_csv);
            codec.reset();
            std::cout << "🎛️  Цифровой кодек включён (M=" << codec_params.bitsM
                      << ", Q=" << codec_params.bitsQ << ", fun=" << codec_params.funType << ")\n";
            
            // Запускаем приём кадров в отдельном потоке для кодека (если НЕ режим сообщений)
            if (!message_mode)
            {
                receive_thread = std::thread(receive_frames_codec, tap_fd, sock, &codec);
                std::cout << "🔄 Двунаправленная передача включена (кодек)\n";
            }
        } catch (const std::exception &e) {
            std::cerr << "❌ Ошибка инициализации кодека: " << e.what() << "\n";
            return 1;
        }
    }

    if (message_mode)
    {
        // Режим текстовых сообщений
        std::cout << "💬 Режим отправки сообщений. Вводите текст:\n";
        std::string user_message;
        while (std::getline(std::cin, user_message))
        {
            if (user_message.empty())
                continue;

            if (use_codec)
            {
                // РЕЖИМ КОДЕКА: кодируем полноценное сообщение с фреймингом
                std::vector<uint8_t> payload(user_message.begin(), user_message.end());
                std::vector<uint8_t> framed = codec.encodeMessage(payload);
                sendto(sock, framed.data(), framed.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
                std::cout << "📤 Сообщение закодировано и отправлено (" << framed.size() << " байт)\n";
            }
            else
            {
                // СТАРЫЙ РЕЖИМ: libsodium AEAD шифрование
                // Считаем SHA-256 от текста
                unsigned char hash_buf[HASH_SIZE];
                crypto_hash_sha256(hash_buf,
                                   reinterpret_cast<const unsigned char *>(user_message.data()),
                                   user_message.size());

                // Сформируем plaintext = [32 байта хеша] + [исходный текст]
                std::vector<unsigned char> plaintext;
                plaintext.insert(plaintext.end(), hash_buf, hash_buf + HASH_SIZE);
                plaintext.insert(plaintext.end(),
                                 reinterpret_cast<const unsigned char *>(user_message.data()),
                                 reinterpret_cast<const unsigned char *>(user_message.data()) + user_message.size());

                // Генерируем nonce
                randombytes_buf(nonce.data(), nonce.size());

                // Реальный размер plaintext — это (32 + длина сообщения)
                std::vector<unsigned char> encrypted(plaintext.size() + crypto_aead_chacha20poly1305_IETF_ABYTES);
                unsigned long long encrypted_len = 0;

                // Шифруем (ChaCha20-Poly1305)
                crypto_aead_chacha20poly1305_ietf_encrypt(
                    encrypted.data(), &encrypted_len,
                    plaintext.data(), plaintext.size(),
                    nullptr, 0, nullptr,
                    nonce.data(), tx_key.data());

                // Готовим пакет = nonce + ciphertext
                std::vector<unsigned char> packet;
                packet.insert(packet.end(), nonce.begin(), nonce.end());
                packet.insert(packet.end(), encrypted.begin(), encrypted.begin() + encrypted_len);

                // Отправляем
                sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
                std::cout << "📤 Сообщение отправлено (" << user_message.size() << " байт)\n";
            }
        }
    }
    else
    {
        // Режим отправки Ethernet-кадров из tap
        while (true)
        {
            unsigned char buffer[MAX_PACKET_SIZE];
            ssize_t nread = read(tap_fd, buffer, sizeof(buffer));
            if (nread <= 0) continue;

            if (use_codec)
            {
                // Кодек: кодируем кадр целиком как сообщение и отправляем напрямую
                std::vector<uint8_t> payload(buffer, buffer + nread);
                std::vector<uint8_t> framed = codec.encodeMessage(payload);
                sendto(sock, framed.data(), framed.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
                std::cout << "📤 Отправлен кодированный кадр (" << nread << " байт)\n";
            }
            else
            {
                // Старый режим: AEAD
                unsigned char hash_buf[HASH_SIZE];
                crypto_hash_sha256(hash_buf, buffer, nread);
                std::vector<unsigned char> plaintext;
                plaintext.insert(plaintext.end(), hash_buf, hash_buf + HASH_SIZE);
                plaintext.insert(plaintext.end(), buffer, buffer + nread);
                randombytes_buf(nonce.data(), nonce.size());
                std::vector<unsigned char> encrypted(plaintext.size() + crypto_aead_chacha20poly1305_IETF_ABYTES);
                unsigned long long encrypted_len = 0;
                crypto_aead_chacha20poly1305_ietf_encrypt(
                    encrypted.data(), &encrypted_len,
                    plaintext.data(), plaintext.size(),
                    nullptr, 0, nullptr,
                    nonce.data(), tx_key.data());
                std::vector<unsigned char> packet;
                packet.insert(packet.end(), nonce.begin(), nonce.end());
                packet.insert(packet.end(), encrypted.begin(), encrypted.begin() + encrypted_len);
                sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
                std::cout << "📤 Отправлен зашифрованный кадр (" << nread << " байт)\n";
            }
        }
    }

    close(tap_fd);
    close(sock);
    return 0;
}
