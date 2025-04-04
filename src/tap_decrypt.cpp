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
#include <thread>
#include <chrono>
#include <sstream>
#include <iomanip>

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
    const char *ip_str = "0.0.0.0"; // слушаем все интерфейсы по умолчанию
    int port = 12345;

    if (argc == 2)
    {
        port = std::stoi(argv[1]);
    }
    else if (argc >= 3)
    {
        ip_str = argv[1];
        port = std::stoi(argv[2]);
    }

    std::cout << "🌐 Ожидаем пакеты на IP: " << ip_str << ", порт: " << port << "\n";

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
    local_addr.sin_port = htons(port);
    if (inet_pton(AF_INET, ip_str, &local_addr.sin_addr) <= 0)
    {
        std::cerr << "❌ Неверный IP-адрес\n";
        return 1;
    }

    if (bind(sock, (sockaddr *)&local_addr, sizeof(local_addr)) < 0)
    {
        perror("❌ bind() не удался");
        return 1;
    }
    // std::cout << "✅ bind() выполнен успешно\n";

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

        if (message_mode)
        {
            std::string received_msg(reinterpret_cast<char *>(decrypted.data()), decrypted_len);
            std::cout << "📩 Получено сообщение: " << received_msg << "\n";
        }
        else
        {

            // Записываем расшифрованный кадр в tap1
            write(tap_fd, decrypted.data(), decrypted_len);
            std::cout << "✅ Принят и расшифрован кадр (" << decrypted_len << " байт)\n";

            // Сохраняем в файл для проверки
            std::ofstream out("decrypted_frame.bin", std::ios::binary);
            out.write((char *)decrypted.data(), decrypted_len);
            out.close();

            // ⏳ Даем tap_encrypt немного времени записать last_frame.bin
            std::this_thread::sleep_for(std::chrono::milliseconds(5));

            // Сравнение с оригиналом
            std::ifstream original("last_frame.bin", std::ios::binary);
            std::vector<unsigned char> original_frame(
                (std::istreambuf_iterator<char>(original)),
                std::istreambuf_iterator<char>());
            original.close();

            unsigned char hash1[crypto_hash_sha256_BYTES];
            crypto_hash_sha256(hash1, decrypted.data(), decrypted_len);

            // Чтение первой строки из файла с ожидаемым хешем
            std::ifstream hashlog("sent_hashes.log");
            std::string hash_line;
            if (std::getline(hashlog, hash_line))
            {
                unsigned char expected[crypto_hash_sha256_BYTES];
                std::stringstream ss(hash_line);

                for (int i = 0; i < crypto_hash_sha256_BYTES; ++i)
                {
                    std::string byte_hex;
                    ss >> byte_hex;
                    expected[i] = static_cast<unsigned char>(std::stoul(byte_hex, nullptr, 16));
                }

                if (std::memcmp(hash1, expected, crypto_hash_sha256_BYTES) == 0)
                {
                    std::cout << "✅ Хеши совпадают — кадр корректен\n";
                }
                else
                {
                    std::cerr << "❌ Ошибка: хеши не совпадают — кадр повреждён\n";
                }
                // Удаляем первую строку из sent_hashes.log
                std::ifstream fin("sent_hashes.log");
                std::ofstream fout("sent_hashes.tmp");

                std::string skip_line;
                std::getline(fin, skip_line); // Пропускаем первую строку

                std::string line;
                while (std::getline(fin, line))
                {
                    fout << line << "\n";
                }

                fin.close();
                fout.close();
                std::remove("sent_hashes.log");
                std::rename("sent_hashes.tmp", "sent_hashes.log");
            }
            else
            {
                std::cerr << "⚠️ Не удалось прочитать хеш из sent_hashes.log — сравнение пропущено\n";
            }
        }
    }

    close(tap_fd);
    close(sock);
    return 0;
}
