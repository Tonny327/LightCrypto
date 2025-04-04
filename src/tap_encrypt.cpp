#include <iostream>
#include <fstream>
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
#include <iomanip>     // для std::setw, std::setfill

constexpr size_t MAX_PACKET_SIZE = 2000;
constexpr size_t KEY_SIZE = crypto_aead_chacha20poly1305_IETF_KEYBYTES;
constexpr size_t NONCE_SIZE = crypto_aead_chacha20poly1305_IETF_NPUBBYTES;

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

int main(int argc, char *argv[])
{

    bool message_mode = false;
    if (argc >= 2 && std::string(argv[1]) == "--msg")
    {
        message_mode = true;
        argv++;
        argc--;
    }

    if (sodium_init() < 0)
    {
        std::cerr << "Не удалось инициализировать libsodium\n";
        return 1;
    }
    const char *ip_str = "127.0.0.1";
    int port = 12345;

    if (argc >= 2)
        ip_str = argv[1];
    if (argc >= 3)
        port = std::stoi(argv[2]);

    std::cout << "🌐 Используем IP: " << ip_str << ", порт: " << port << "\n";

    std::string ping_cmd = "ping -c 1 " + std::string(ip_str) + " > /dev/null 2>&1";
    int ping_result = system(ping_cmd.c_str());

    if (ping_result != 0)
    {
        std::cout << "⚠️  Внимание: IP-адрес " << ip_str << " недоступен (ping не прошёл)\n";
        std::cout << "Продолжить отправку данных? [y/N]: ";

        std::string answer;
        std::getline(std::cin, answer);
        if (answer != "y" && answer != "Y")
        {
            std::cout << "🚫 Отправка отменена пользователем.\n";
            return 1;
        }
    }
    else
    {
        std::cout << "✅ IP-адрес " << ip_str << " доступен, начинаем работу...\n";
    }

    int tap_fd = open_tap("tap0");
    std::cout << "📡 tap0 открыт для чтения Ethernet-кадров\n";

    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
    {
        perror("socket");
        return 1;
    }

    sockaddr_in dest_addr{};
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(port);
    if (inet_pton(AF_INET, ip_str, &dest_addr.sin_addr) <= 0)
    {
        std::cerr << "❌ Неверный IP-адрес\n";
        return 1;
    }

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

    // 3. Вычисляем общий ключ (tx_key)
    std::vector<unsigned char> key(KEY_SIZE);
    if (crypto_kx_client_session_keys(nullptr, key.data(),
                                      my_public_key, my_private_key,
                                      receiver_public_key) != 0)
    {
        std::cerr << "❌ Ошибка при расчёте общего ключа (client)\n";
        return 1;
    }

    std::vector<unsigned char> nonce(NONCE_SIZE);

    if (message_mode)
    {
        std::cout << "💬 Режим отправки сообщений. Вводите текст:\n";
        std::string user_message;
        while (std::getline(std::cin, user_message))
        {
            if (user_message.empty())
                continue;

            randombytes_buf(nonce.data(), nonce.size());

            std::vector<unsigned char> encrypted(user_message.size() + crypto_aead_chacha20poly1305_IETF_ABYTES);
            unsigned long long encrypted_len = 0;

            crypto_aead_chacha20poly1305_ietf_encrypt(
                encrypted.data(), &encrypted_len,
                reinterpret_cast<const unsigned char *>(user_message.data()), user_message.size(),
                nullptr, 0, nullptr,
                nonce.data(), key.data());

            std::vector<unsigned char> packet;
            packet.insert(packet.end(), nonce.begin(), nonce.end());
            packet.insert(packet.end(), encrypted.begin(), encrypted.begin() + encrypted_len);

            sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
            std::cout << "📤 Сообщение отправлено (" << user_message.size() << " байт)\n";
        }
    }
    else
    {

        while (true)
        {
            unsigned char buffer[MAX_PACKET_SIZE];
            ssize_t nread = read(tap_fd, buffer, sizeof(buffer));
            if (nread <= 0)
                continue;

            randombytes_buf(nonce.data(), nonce.size());

            std::vector<unsigned char> encrypted(nread + crypto_aead_chacha20poly1305_IETF_ABYTES);
            unsigned long long encrypted_len = 0;

            crypto_aead_chacha20poly1305_ietf_encrypt(
                encrypted.data(), &encrypted_len,
                buffer, nread,
                nullptr, 0, nullptr,
                nonce.data(), key.data());

            // Сохраняем исходный кадр для теста
            std::ofstream log("last_frame.bin", std::ios::binary);
            log.write((char *)buffer, nread);
            log.close();

            // nonce + encrypted
            std::vector<unsigned char> packet;
            packet.insert(packet.end(), nonce.begin(), nonce.end());
            packet.insert(packet.end(), encrypted.begin(), encrypted.begin() + encrypted_len);

            unsigned char hash_src[crypto_hash_sha256_BYTES];
            crypto_hash_sha256(hash_src, buffer, nread);

            std::ofstream hashlog("sent_hashes.log", std::ios::app);
            for (int i = 0; i < crypto_hash_sha256_BYTES; ++i)
                hashlog << std::hex << std::setw(2) << std::setfill('0') << (int)hash_src[i] << " ";
            hashlog << std::endl;
            hashlog.close();

            sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
            std::cout << "📤 Отправлен зашифрованный кадр (" << nread << " байт)\n";
        }
    }

    close(tap_fd);
    close(sock);
    return 0;
}
