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
        perror("ioctl TUNSETIFF");
        close(fd);
        exit(1);
    }

    return fd;
}
void send_frames(int tap_fd, int sock, const sockaddr_in &dest_addr, const std::vector<unsigned char> &key)
{
    std::vector<unsigned char> nonce(NONCE_SIZE);
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        ssize_t nread = read(tap_fd, buffer, sizeof(buffer));
        if (nread <= 0)
            continue;

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
            nonce.data(), key.data());

        std::vector<unsigned char> packet;
        packet.insert(packet.end(), nonce.begin(), nonce.end());
        packet.insert(packet.end(), encrypted.begin(), encrypted.begin() + encrypted_len);

        sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
        std::cout << "📤 Отправлен зашифрованный кадр из tap1 (" << nread << " байт)\n";
    }
}

int main(int argc, char *argv[])
{

    // --msg: если true, тогда мы интерпретируем расшифрованные данные как строку
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

    // Параметры: IP и порт, на котором слушаем
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

    // Создаём UDP-сокет
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

    // Создаём второй сокет для отправки
    int send_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (send_sock < 0)
    {
        perror("send socket");
        return 1;
    }

    // Запускаем отправку кадров в отдельном потоке
    std::thread send_thread(send_frames, tap_fd, send_sock, sender_addr, std::ref(key));

    // Основной цикл приёма
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        sockaddr_in sender_addr{};
        socklen_t sender_len = sizeof(sender_addr);

        // Принимаем UDP-пакет
        ssize_t nrecv = recvfrom(sock, buffer, sizeof(buffer), 0, (sockaddr *)&sender_addr, &sender_len);
        if (nrecv <= NONCE_SIZE)
            continue;

        // Разделяем nonce и ciphertext
        std::vector<unsigned char> nonce(buffer, buffer + NONCE_SIZE);
        std::vector<unsigned char> ciphertext(buffer + NONCE_SIZE, buffer + nrecv);

        // Расшифровываем
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

        // Проверяем, что длина хотя бы 32 байта (под хеш)
        if (decrypted_len < HASH_SIZE)
        {
            std::cerr << "❌ Слишком маленький расшифрованный буфер!\n";
            continue;
        }

        // Первые 32 байта — это хеш
        unsigned char received_hash[HASH_SIZE];
        std::memcpy(received_hash, decrypted.data(), HASH_SIZE);

        // Остальная часть – это сообщение
        size_t msg_len = decrypted_len - HASH_SIZE;

        // Считаем свой хеш
        unsigned char actual_hash[HASH_SIZE];
        crypto_hash_sha256(actual_hash,
                           decrypted.data() + HASH_SIZE, // данные начинаются через 32 байта
                           msg_len);

        // Сравниваем
        if (std::memcmp(received_hash, actual_hash, HASH_SIZE) != 0)
        {
            std::cerr << "❌ Хеш не совпадает — данные повреждены!\n";
            continue;
        }

        if (message_mode)
        {
            // Теперь выводим сообщение:
            std::string received_msg(
                reinterpret_cast<char *>(decrypted.data() + HASH_SIZE),
                msg_len);
            std::cout << "📩 Получено сообщение: "
                      << msg_len << " байт): "
                      << received_msg << "\n";
        }
        else
        {
            size_t data_len = decrypted_len - HASH_SIZE;
            std::vector<unsigned char> data_buf(data_len);
            std::memcpy(data_buf.data(), decrypted.data() + HASH_SIZE, data_len);

            // Пишем расшифрованный (и проверенный) кадр в tap1
            write(tap_fd, data_buf.data(), data_len);

            std::cout << "✅ Принят и расшифрован кадр (" << data_len << " байт)\n";
            std::cout << "✅ Хеши совпадают — кадр корректен\n";
        }
    }

    close(tap_fd);
    close(sock);
    return 0;
}
