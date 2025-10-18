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
#include <chrono>
#include <iomanip>
#include "digital_codec.h"
#include "file_transfer.h"

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

void send_frames_codec(int tap_fd, int sock, const sockaddr_in &dest_addr, digitalcodec::DigitalCodec *codec)
{
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        ssize_t nread = read(tap_fd, buffer, sizeof(buffer));
        if (nread <= 0)
            continue;

        std::vector<uint8_t> payload(buffer, buffer + nread);
        std::vector<uint8_t> framed = codec->encodeMessage(payload);
        sendto(sock, framed.data(), framed.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
        std::cout << "📤 Отправлен кодированный кадр из tap1 (" << nread << " байт)\n";
    }
}

// Функция приема файла через libsodium
bool receive_file_libsodium(int sock, const std::vector<unsigned char> &rx_key, const std::string &output_path)
{
    std::cout << "📥 Ожидание файла через libsodium...\n";
    
    filetransfer::FileReceiver receiver;
    bool header_received = false;
    std::string filename;
    
    while (true) {
        unsigned char buffer[MAX_PACKET_SIZE];
        ssize_t nrecv = recv(sock, buffer, sizeof(buffer), 0);
        
        if (nrecv <= NONCE_SIZE) {
            continue;
        }
        
        // Расшифровываем пакет
        std::vector<unsigned char> nonce(buffer, buffer + NONCE_SIZE);
        std::vector<unsigned char> ciphertext(buffer + NONCE_SIZE, buffer + nrecv);
        std::vector<unsigned char> decrypted(ciphertext.size());
        unsigned long long decrypted_len = 0;
        
        int result = crypto_aead_chacha20poly1305_ietf_decrypt(
            decrypted.data(), &decrypted_len,
            nullptr,
            ciphertext.data(), ciphertext.size(),
            nullptr, 0,
            nonce.data(), rx_key.data());
        
        if (result != 0) {
            std::cerr << "❌ Ошибка расшифровки пакета\n";
            continue;
        }
        
        // Проверяем, это заголовок или чанк
        if (!header_received) {
            // Пытаемся распарсить как заголовок файла
            filetransfer::FileHeader header;
            if (filetransfer::deserialize_file_header(decrypted.data(), decrypted_len, header, filename)) {
                std::cout << "📥 Получен заголовок файла: " << filename << "\n";
                receiver.initialize(header, filename);
                header_received = true;
                continue;
            }
        }
        
        // Пытаемся распарсить как чанк
        filetransfer::ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (filetransfer::deserialize_chunk(decrypted.data(), decrypted_len, chunk_header, chunk_data)) {
            receiver.add_chunk(chunk_header, chunk_data);
            
            // Проверяем, все ли чанки получены
            if (receiver.is_complete()) {
                std::cout << "✅ Все чанки получены, сохраняем файл...\n";
                
                // Формируем путь для сохранения
                std::string save_path = output_path;
                if (save_path == "./received_file") {
                    save_path = "./" + filename;
                }
                
                if (receiver.save_file(save_path)) {
                    return true;
                } else {
                    std::cerr << "❌ Ошибка при сохранении файла\n";
                    return false;
                }
            }
        }
    }
    
    return false;
}

// Функция приема файла через кодек
bool receive_file_codec(int sock, digitalcodec::DigitalCodec *codec, const std::string &output_path)
{
    std::cout << "📥 Ожидание файла через кодек...\n";
    
    filetransfer::FileReceiver receiver;
    bool header_received = false;
    std::string filename;
    
    while (true) {
        unsigned char buffer[MAX_PACKET_SIZE];
        ssize_t nrecv = recv(sock, buffer, sizeof(buffer), 0);
        
        if (nrecv <= 0) {
            continue;
        }
        
        // Декодируем пакет
        std::vector<uint8_t> framed(buffer, buffer + nrecv);
        std::vector<uint8_t> decoded_bytes = codec->decodeMessage(framed, 0);
        
        if (decoded_bytes.empty()) {
            std::cerr << "❌ Ошибка декодирования пакета\n";
            continue;
        }
        
        // Проверяем, это заголовок или чанк
        if (!header_received) {
            // Пытаемся распарсить как заголовок файла
            filetransfer::FileHeader header;
            if (filetransfer::deserialize_file_header(decoded_bytes.data(), decoded_bytes.size(), header, filename)) {
                std::cout << "📥 Получен заголовок файла через кодек: " << filename << "\n";
                receiver.initialize(header, filename);
                header_received = true;
                continue;
            }
        }
        
        // Пытаемся распарсить как чанк
        filetransfer::ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (filetransfer::deserialize_chunk(decoded_bytes.data(), decoded_bytes.size(), chunk_header, chunk_data)) {
            receiver.add_chunk(chunk_header, chunk_data);
            
            // Проверяем, все ли чанки получены
            if (receiver.is_complete()) {
                std::cout << "✅ Все чанки получены через кодек, сохраняем файл...\n";
                
                // Формируем путь для сохранения
                std::string save_path = output_path;
                if (save_path == "./received_file") {
                    save_path = "./" + filename;
                }
                
                if (receiver.save_file(save_path)) {
                    return true;
                } else {
                    std::cerr << "❌ Ошибка при сохранении файла\n";
                    return false;
                }
            }
        }
    }
    
    return false;
}

int main(int argc, char *argv[])
{
    // --msg: если true, тогда мы интерпретируем расшифрованные данные как строку
    bool message_mode = false;
    bool file_mode = false;
    std::string output_path = "./received_file";
    bool use_codec = false;
    std::string codec_csv;
    digitalcodec::CodecParams codec_params;

    std::vector<std::string> positionals;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--msg") { message_mode = true; continue; }
        if (arg == "--file") { file_mode = true; continue; }
        if (arg == "--output" && i + 1 < argc) { output_path = argv[++i]; continue; }
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

    // Параметры: IP и порт, на котором слушаем
    const char *ip_str = "0.0.0.0"; // слушаем все интерфейсы по умолчанию
    int port = 12345;

    if (positionals.size() == 1) { port = std::stoi(positionals[0]); }
    else if (positionals.size() >= 2) { ip_str = positionals[0].c_str(); port = std::stoi(positionals[1]); }

    std::cout << "🌐 Ожидаем пакеты на IP: " << ip_str << ", порт: " << port << "\n";

    // Открываем tap1 только если не режим файлов
    int tap_fd = -1;
    if (!file_mode) {
        tap_fd = open_tap("tap1");
        std::cout << "📡 tap1 открыт для записи расшифрованных Ethernet-кадров\n";
    }

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

    // Объявляем ключи для всех режимов
    std::vector<unsigned char> rx_key(KEY_SIZE);
    std::vector<unsigned char> tx_key(KEY_SIZE);
    std::thread send_thread;

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

        // 3. Вычисляем ключи (rx/tx)
        if (crypto_kx_server_session_keys(
                rx_key.data(), tx_key.data(),
                my_public_key, my_private_key,
                sender_public_key) != 0)
        {
            std::cerr << "❌ Ошибка при расчёте общего ключа (server)\n";
            return 1;
        }

        // Запускаем отправку кадров в отдельном потоке ТОЛЬКО если НЕ режим сообщений и НЕ режим файлов
        if (!message_mode && !file_mode)
        {
            // Создаём второй сокет для отправки
            int send_sock = socket(AF_INET, SOCK_DGRAM, 0);
            if (send_sock < 0)
            {
                perror("send socket");
                return 1;
            }

            send_thread = std::thread(send_frames, tap_fd, send_sock, sender_addr, std::ref(tx_key));
            std::cout << "🔄 Двунаправленная передача включена\n";
        }
    }

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
        } catch (const std::exception &e) {
            std::cerr << "❌ Ошибка инициализации кодека: " << e.what() << "\n";
            return 1;
        }
    }
    
    // Для режима кодека без message_mode нужно запустить поток отправки
    // но сначала получим адрес отправителя из первого пакета
    bool send_thread_started = false;

    // Режим приёма файлов
    if (file_mode)
    {
        if (use_codec)
        {
            if (!receive_file_codec(sock, &codec, output_path)) {
                std::cerr << "❌ Ошибка при приёме файла через кодек\n";
                close(sock);
                if (tap_fd >= 0) close(tap_fd);
                return 1;
            }
        }
        else
        {
            if (!receive_file_libsodium(sock, rx_key, output_path)) {
                std::cerr << "❌ Ошибка при приёме файла через libsodium\n";
                close(sock);
                if (tap_fd >= 0) close(tap_fd);
                return 1;
            }
        }
        
        // Файл успешно получен, завершаем программу
        close(sock);
        if (tap_fd >= 0) close(tap_fd);
        return 0;
    }

    // Основной цикл приёма (для режимов сообщений и кадров)
    while (true)
    {
        unsigned char buffer[MAX_PACKET_SIZE];
        sockaddr_in sender_addr{};
        socklen_t sender_len = sizeof(sender_addr);

        // Принимаем UDP-пакет
        ssize_t nrecv = recvfrom(sock, buffer, sizeof(buffer), 0, (sockaddr *)&sender_addr, &sender_len);
        if (nrecv <= 0)
            continue;

        // Запускаем поток отправки после получения первого пакета (для кодека)
        if (use_codec && !message_mode && !file_mode && !send_thread_started)
        {
            int send_sock = socket(AF_INET, SOCK_DGRAM, 0);
            if (send_sock < 0)
            {
                perror("send socket for codec");
            }
            else
            {
                send_thread = std::thread(send_frames_codec, tap_fd, send_sock, sender_addr, &codec);
                send_thread_started = true;
                std::cout << "🔄 Двунаправленная передача включена (кодек)\n";
            }
        }

        if (use_codec && message_mode)
        {
            // РЕЖИМ КОДЕКА: принимаем полнофреймовое сообщение и восстанавливаем исходный текст
            std::vector<uint8_t> framed(buffer, buffer + nrecv);
            std::vector<uint8_t> decoded_bytes = codec.decodeMessage(framed, 0 /*len из кадра*/);
            if (decoded_bytes.empty())
            {
                std::cerr << "❌ Критическая ошибка декодирования сообщения (буфер пуст)!\n";
                continue;
            }
            std::string received_msg(decoded_bytes.begin(), decoded_bytes.end());
            std::cout << "📩 Получено сообщение (" << received_msg.size() << " байт): \"" << received_msg << "\"\n";
        }
        else
        {
            if (use_codec)
            {
                // РЕЖИМ КОДЕКА: принимаем кодированный кадр и пишем его payload в tap1
                std::vector<uint8_t> framed(buffer, buffer + nrecv);
                std::vector<uint8_t> decoded_bytes = codec.decodeMessage(framed, 0);
                if (!message_mode)
                {
                    if (decoded_bytes.empty())
                    {
                        std::cerr << "❌ Критическая ошибка декодирования кадра (буфер пуст)!\n";
                        continue;
                    }
                    write(tap_fd, decoded_bytes.data(), decoded_bytes.size());
                    std::cout << "✅ Принят и раскодирован кадр (" << decoded_bytes.size() << " байт)\n";
                }
                else
                {
                    if (decoded_bytes.empty())
                    {
                        std::cerr << "❌ Критическая ошибка декодирования сообщения (буфер пуст)!\n";
                        continue;
                    }
                    std::string received_msg(decoded_bytes.begin(), decoded_bytes.end());
                    std::cout << "📩 Получено сообщение (" << received_msg.size() << " байт): \"" << received_msg << "\"\n";
                }
            }
            else
            {
                // СТАРЫЙ РЕЖИМ: libsodium AEAD расшифровка
                if (nrecv <= NONCE_SIZE) continue;
                std::vector<unsigned char> nonce(buffer, buffer + NONCE_SIZE);
                std::vector<unsigned char> ciphertext(buffer + NONCE_SIZE, buffer + nrecv);
                std::vector<unsigned char> decrypted(ciphertext.size());
                unsigned long long decrypted_len = 0;
                int result = crypto_aead_chacha20poly1305_ietf_decrypt(
                    decrypted.data(), &decrypted_len,
                    nullptr,
                    ciphertext.data(), ciphertext.size(),
                    nullptr, 0,
                    nonce.data(), rx_key.data());
                if (result != 0) { std::cerr << "❌ Ошибка расшифровки!\n"; continue; }
                if (decrypted_len < HASH_SIZE) { std::cerr << "❌ Слишком маленький расшифрованный буфер!\n"; continue; }
                unsigned char received_hash[HASH_SIZE];
                std::memcpy(received_hash, decrypted.data(), HASH_SIZE);
                size_t data_len = decrypted_len - HASH_SIZE;
                unsigned char actual_hash[HASH_SIZE];
                crypto_hash_sha256(actual_hash, decrypted.data() + HASH_SIZE, data_len);
                
                bool hash_valid = (std::memcmp(received_hash, actual_hash, HASH_SIZE) == 0);
                if (!hash_valid) {
                    std::cerr << "⚠️  Хеш не совпадает — данные могут быть повреждены!\n";
                    std::cerr << "⚠️  Выводим данные для отладки (возможно искажены):\n";
                }
                
                if (message_mode)
                {
                    std::string received_msg(reinterpret_cast<char *>(decrypted.data() + HASH_SIZE), data_len);
                    std::cout << "📩 Получено сообщение (" << data_len << " байт): " << received_msg << "\n";
                }
                else
                {
                    write(tap_fd, decrypted.data() + HASH_SIZE, data_len);
                    std::cout << "✅ Принят и расшифрован кадр (" << data_len << " байт)\n";
                }
            }
        }
    }

    if (tap_fd >= 0) {
        close(tap_fd);
    }
    close(sock);
    return 0;
}
