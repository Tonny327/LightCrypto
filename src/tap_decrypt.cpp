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
        perror("ioctl TUNSETIFF");
        close(fd);
        exit(1);
    }

    return fd;
}

int main()
{
    if (sodium_init() < 0)
    {
        std::cerr << "Не удалось инициализировать libsodium\n";
        return 1;
    }

    int tap_fd = open_tap("tap1");
    std::cout << "📡 tap1 открыт для записи расшифрованных Ethernet-кадров\n";

    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
    {
        perror("socket");
        return 1;
    }

    sockaddr_in local_addr{};
    local_addr.sin_family = AF_INET;
    local_addr.sin_port = htons(12345);
    local_addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(sock, (sockaddr *)&local_addr, sizeof(local_addr)) < 0)
    {
        perror("bind");
        return 1;
    }

    // === [Автоматический обмен ключами через UDP] ===
    unsigned char my_public_key[crypto_kx_PUBLICKEYBYTES];
    unsigned char my_private_key[crypto_kx_SECRETKEYBYTES];
    crypto_kx_keypair(my_public_key, my_private_key);

    // 1. Принимаем публичный ключ отправителя
    unsigned char sender_public_key[crypto_kx_PUBLICKEYBYTES];
    sockaddr_in sender_addr{};
    socklen_t sender_len = sizeof(sender_addr);

    ssize_t received = recvfrom(sock, sender_public_key, crypto_kx_PUBLICKEYBYTES, 0,
                                (sockaddr *)&sender_addr, &sender_len);
    if (received != crypto_kx_PUBLICKEYBYTES)
    {
        std::cerr << "❌ Ошибка при получении публичного ключа отправителя\n";
        return 1;
    }
    std::cout << "📥 Публичный ключ отправителя получен\n";

    // 2. Отправляем свой публичный ключ обратно
    sendto(sock, my_public_key, crypto_kx_PUBLICKEYBYTES, 0,
           (sockaddr *)&sender_addr, sender_len);
    std::cout << "📤 Отправлен свой публичный ключ отправителю\n";

    // 3. Вычисляем общий ключ (rx_key)
    std::vector<unsigned char> key(KEY_SIZE);
    if (crypto_kx_server_session_keys(
            key.data(), nullptr,
            my_public_key, my_private_key,
            sender_public_key) != 0)
    {
        std::cerr << "❌ Ошибка при расчёте общего ключа (server)\n";
        return 1;
    }


    
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        sockaddr_in sender_addr{};
        socklen_t sender_len = sizeof(sender_addr);

        ssize_t nrecv = recvfrom(sock, buffer, sizeof(buffer), 0, (sockaddr *)&sender_addr, &sender_len);
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
            std::cerr << "❌ Ошибка расшифровки!\n";
            continue;
        }

        // Записываем расшифрованный кадр в tap1
        write(tap_fd, decrypted.data(), decrypted_len);
        std::cout << "✅ Принят и расшифрован кадр (" << decrypted_len << " байт)\n";

        // Сохраняем в файл для проверки
        std::ofstream out("decrypted_frame.bin", std::ios::binary);
        out.write((char *)decrypted.data(), decrypted_len);
        out.close();

        // Сравнение с оригиналом
        std::ifstream original("last_frame.bin", std::ios::binary);
        std::vector<unsigned char> original_frame(
            (std::istreambuf_iterator<char>(original)),
            std::istreambuf_iterator<char>());
        original.close();

        if (original_frame.size() != decrypted_len ||
            !std::equal(original_frame.begin(), original_frame.end(), decrypted.begin()))
        {
            std::cerr << "❌ Ошибка: расшифрованный кадр не совпадает с оригиналом\n";

            // вывод рассшифрованных байтов
            // std::cout << "🔓 Расшифрованные данные:\n";
            // for (size_t i = 0; i < std::min((size_t)32, (size_t)decrypted_len); ++i)
            //     std::printf("%02x ", decrypted[i]);
            // std::cout << "\n";
        }
        else
        {
            std::cout << "✅ Расшифрованный кадр совпадает с оригиналом\n";

            // вывод рассшифрованных байтов
            // std::cout << "🔓 Расшифрованные данные:\n";
            // for (size_t i = 0; i < std::min((size_t)32, (size_t)decrypted_len); ++i)
            //     std::printf("%02x ", decrypted[i]);
            // std::cout << "\n";
        
        }
    }

    close(tap_fd);
    close(sock);
    return 0;
}
