#include <iostream>
#include <vector>
#include <cstring>
#include <cerrno>
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


constexpr size_t MAX_PACKET_SIZE = 16000;  // Увеличено для поддержки Custom Codec (коэффициент расширения ~4x)
constexpr size_t KEY_SIZE = crypto_aead_chacha20poly1305_IETF_KEYBYTES;
constexpr size_t NONCE_SIZE = crypto_aead_chacha20poly1305_IETF_NPUBBYTES;
constexpr size_t HASH_SIZE = crypto_hash_sha256_BYTES;

// Функция отправки синхронизации состояний кодека
bool send_codec_sync(int sock, const sockaddr_in &dest_addr, digitalcodec::DigitalCodec *codec) {
    std::vector<uint8_t> sync_packet;
    sync_packet.push_back(0xFF); // Маркер синхронизации
    sync_packet.push_back(0xFE);
    sync_packet.push_back(0xFD);
    sync_packet.push_back(0xFC);
    
    // Добавляем текущие состояния кодека (4 байта каждое, little-endian)
    int32_t h1 = codec->get_enc_h1();
    int32_t h2 = codec->get_enc_h2();
    sync_packet.push_back(h1 & 0xFF);
    sync_packet.push_back((h1 >> 8) & 0xFF);
    sync_packet.push_back((h1 >> 16) & 0xFF);
    sync_packet.push_back((h1 >> 24) & 0xFF);
    sync_packet.push_back(h2 & 0xFF);
    sync_packet.push_back((h2 >> 8) & 0xFF);
    sync_packet.push_back((h2 >> 16) & 0xFF);
    sync_packet.push_back((h2 >> 24) & 0xFF);
    
    // Отправляем пакет синхронизации
    if (sendto(sock, sync_packet.data(), sync_packet.size(), 0, 
              (sockaddr *)&dest_addr, sizeof(dest_addr)) < 0) {
        std::cerr << "❌ Ошибка отправки синхронизации: " << strerror(errno) << "\n";
        return false;
    }
    
    std::cout << "🔄 Синхронизация состояний по запросу: h1=" << h1 << ", h2=" << h2 << "\n";
    return true;
}

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

// Функция отправки файла через libsodium
bool send_file_libsodium(int sock, const sockaddr_in &dest_addr, const std::vector<unsigned char> &tx_key,
                          const std::string &file_path)
{
    std::cout << "📁 Начинаем отправку файла: " << file_path << "\n";
    
    // Загружаем файл
    filetransfer::FileSender sender;
    if (!sender.load_file(file_path)) {
        return false;
    }
    
    // Запоминаем время начала передачи
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::vector<unsigned char> nonce(NONCE_SIZE);
    
    // 1. Отправляем заголовок файла
    auto header_bytes = filetransfer::serialize_file_header(sender.get_header(), sender.get_filename());
    
    // Шифруем заголовок
    randombytes_buf(nonce.data(), nonce.size());
    std::vector<unsigned char> encrypted_header(header_bytes.size() + crypto_aead_chacha20poly1305_IETF_ABYTES);
    unsigned long long encrypted_len = 0;
    
    crypto_aead_chacha20poly1305_ietf_encrypt(
        encrypted_header.data(), &encrypted_len,
        header_bytes.data(), header_bytes.size(),
        nullptr, 0, nullptr,
        nonce.data(), tx_key.data());
    
    std::vector<unsigned char> packet;
    packet.insert(packet.end(), nonce.begin(), nonce.end());
    packet.insert(packet.end(), encrypted_header.begin(), encrypted_header.begin() + encrypted_len);
    
    sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
    std::cout << "📤 Заголовок файла отправлен\n";
    
    // Небольшая задержка для обработки заголовка
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    // 2. Отправляем чанки
    uint32_t total_chunks = sender.get_total_chunks();
    for (uint32_t i = 0; i < total_chunks; i++) {
        filetransfer::ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (!sender.get_chunk(i, chunk_header, chunk_data)) {
            std::cerr << "❌ Ошибка получения чанка " << i << "\n";
            return false;
        }
        
        // Сериализуем чанк
        auto chunk_bytes = filetransfer::serialize_chunk(chunk_header, chunk_data.data());
        
        // Шифруем чанк
        randombytes_buf(nonce.data(), nonce.size());
        std::vector<unsigned char> encrypted_chunk(chunk_bytes.size() + crypto_aead_chacha20poly1305_IETF_ABYTES);
        encrypted_len = 0;
        
        crypto_aead_chacha20poly1305_ietf_encrypt(
            encrypted_chunk.data(), &encrypted_len,
            chunk_bytes.data(), chunk_bytes.size(),
            nullptr, 0, nullptr,
            nonce.data(), tx_key.data());
        
        packet.clear();
        packet.insert(packet.end(), nonce.begin(), nonce.end());
        packet.insert(packet.end(), encrypted_chunk.begin(), encrypted_chunk.begin() + encrypted_len);
        
        sendto(sock, packet.data(), packet.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
        
        // Показываем прогресс
        float progress = (100.0f * (i + 1)) / total_chunks;
        std::cout << "📤 Отправлен чанк " << (i + 1) << "/" << total_chunks 
                  << " (" << chunk_header.data_size << " байт, "
                  << std::fixed << std::setprecision(1) << progress << "%)\n";
        
        // Небольшая задержка между чанками
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    }
    
    // Вычисляем время передачи и скорость
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    double seconds = duration.count() / 1000.0;
    double file_size_mb = sender.get_header().file_size / (1024.0 * 1024.0);
    double speed_mbps = (seconds > 0) ? (file_size_mb / seconds) : 0.0;
    double speed_mbitps = speed_mbps * 8.0; // Конвертируем МБ/сек в Мбит/сек
    
    std::cout << "✅ Все чанки отправлены успешно!\n";
    std::cout << "⏱️  Время передачи: " << std::fixed << std::setprecision(2) << seconds << " сек\n";
    std::cout << "📊 Размер файла: " << std::fixed << std::setprecision(2) << file_size_mb << " МБ\n";
    std::cout << "🚀 Скорость передачи: " << std::fixed << std::setprecision(2) << speed_mbitps << " Мбит/сек\n";
    return true;
}

// Функция отправки файла через кодек
bool send_file_codec(int sock, const sockaddr_in &dest_addr, digitalcodec::DigitalCodec *codec,
                     const std::string &file_path)
{
    std::cout << "📁 Начинаем отправку файла через кодек: " << file_path << "\n";
    
    // Делаем сокет неблокирующим для обработки запросов синхронизации
    int flags = fcntl(sock, F_GETFL, 0);
    fcntl(sock, F_SETFL, flags | O_NONBLOCK);
    
    // Загружаем файл
    filetransfer::FileSender sender;
    if (!sender.load_file(file_path)) {
        return false;
    }
    
    // Запоминаем время начала передачи
    auto start_time = std::chrono::high_resolution_clock::now();
    
    // 0. Начальная синхронизация состояний кодека с получателем
    std::cout << "🔄 Начальная синхронизация состояний кодека...\n";
    if (!send_codec_sync(sock, dest_addr, codec)) {
        std::cerr << "❌ Критическая ошибка: не удалось отправить начальную синхронизацию\n";
        return false;
    }
    std::cout << "✅ Начальная синхронизация отправлена\n";
    
    // Ждем обработки синхронизации
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    
    // 1. Отправляем заголовок файла
    auto header_bytes = filetransfer::serialize_file_header(sender.get_header(), sender.get_filename());
    std::vector<uint8_t> framed_header = codec->encodeMessage(header_bytes);
    
    sendto(sock, framed_header.data(), framed_header.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
    std::cout << "📤 Заголовок файла отправлен через кодек\n";
    
    // Небольшая задержка для обработки заголовка
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    // 2. Отправляем чанки
    uint32_t total_chunks = sender.get_total_chunks();
    for (uint32_t i = 0; i < total_chunks; i++) {
        filetransfer::ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (!sender.get_chunk(i, chunk_header, chunk_data)) {
            std::cerr << "❌ Ошибка получения чанка " << i << "\n";
            return false;
        }
        
        // Сериализуем чанк
        auto chunk_bytes = filetransfer::serialize_chunk(chunk_header, chunk_data.data());
        
        // ВАЖНО: НЕ сбрасываем состояния кодека - они эволюционируют между чанками
        // Это уменьшает количество коллизий и повышает скорость передачи
        // Восстановление после потерь обеспечивается запросами синхронизации от получателя
        
        // Кодируем чанк (состояния продолжают эволюционировать)
        std::vector<uint8_t> framed_chunk = codec->encodeMessage(chunk_bytes);
        
        // DEBUG: Размеры пакетов (раскомментируйте при необходимости)
        // std::cout << "🔍 DEBUG: Чанк " << (i+1) << " - оригинал: " << chunk_bytes.size() 
        //           << " байт, закодирован: " << framed_chunk.size() << " байт\n";
        
        sendto(sock, framed_chunk.data(), framed_chunk.size(), 0, (sockaddr *)&dest_addr, sizeof(dest_addr));
        
        // ВАРИАНТ 1Б: Проверяем наличие запросов синхронизации (неблокирующий режим)
        unsigned char recv_buffer[MAX_PACKET_SIZE];
        sockaddr_in recv_addr{};
        socklen_t recv_len = sizeof(recv_addr);
        ssize_t nrecv = recvfrom(sock, recv_buffer, sizeof(recv_buffer), MSG_DONTWAIT,
                                 (sockaddr *)&recv_addr, &recv_len);
        
        if (nrecv > 0) {
            // Проверяем, это запрос синхронизации?
            filetransfer::SyncRequest sync_req;
            if (filetransfer::deserialize_sync_request(recv_buffer, nrecv, sync_req)) {
                std::cout << "📥 Получен запрос синхронизации (ожидался чанк " 
                          << sync_req.expected_chunk << ")\n";
                std::cout << "🔄 Отправляем синхронизацию состояний...\n";
                
                // Отправляем синхронизацию состояний
                if (send_codec_sync(sock, dest_addr, codec)) {
                    std::cout << "✅ Синхронизация отправлена по запросу\n";
                }
            }
        } else if (nrecv < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
            // Игнорируем EAGAIN/EWOULDBLOCK (нет данных), но логируем другие ошибки
            // std::cerr << "⚠️  Ошибка при проверке запросов синхронизации: " << strerror(errno) << "\n";
        }
        
        // Показываем прогресс
        float progress = (100.0f * (i + 1)) / total_chunks;
        std::cout << "📤 Отправлен чанк " << (i + 1) << "/" << total_chunks 
                  << " (" << chunk_header.data_size << " байт, "
                  << std::fixed << std::setprecision(1) << progress << "%)\n";
        
        // Небольшая задержка между чанками
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    
    // Вычисляем время передачи и скорость
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    double seconds = duration.count() / 1000.0;
    double file_size_mb = sender.get_header().file_size / (1024.0 * 1024.0);
    double speed_mbps = (seconds > 0) ? (file_size_mb / seconds) : 0.0;
    double speed_mbitps = speed_mbps * 8.0; // Конвертируем МБ/сек в Мбит/сек
    
    // Восстанавливаем блокирующий режим сокета
    fcntl(sock, F_SETFL, flags);
    
    std::cout << "✅ Все чанки отправлены успешно через кодек!\n";
    std::cout << "⏱️  Время передачи: " << std::fixed << std::setprecision(2) << seconds << " сек\n";
    std::cout << "📊 Размер файла: " << std::fixed << std::setprecision(2) << file_size_mb << " МБ\n";
    std::cout << "🚀 Скорость передачи: " << std::fixed << std::setprecision(2) << speed_mbitps << " Мбит/сек\n";
    return true;
}

int main(int argc, char *argv[])
{
    bool message_mode = false;
    bool file_mode = false;
    std::string file_path;
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
        if (arg == "--file" && i + 1 < argc) { file_mode = true; file_path = argv[++i]; continue; }
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

    // Открываем tap0 только если не режим файлов
    int tap_fd = -1;
    if (!file_mode) {
        tap_fd = open_tap("tap0");
        std::cout << "📡 tap0 открыт для чтения Ethernet-кадров\n";
    }

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

        // Запускаем приём кадров в отдельном потоке ТОЛЬКО если НЕ режим сообщений и НЕ режим файлов
        if (!message_mode && !file_mode)
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
            codec.reset(); // Восстанавливаем сброс состояний для правильной инициализации
            std::cout << "🎛️  Цифровой кодек включён (M=" << codec_params.bitsM
                      << ", Q=" << codec_params.bitsQ << ", fun=" << codec_params.funType << ")\n";
            
            // Запускаем приём кадров в отдельном потоке для кодека (если НЕ режим сообщений и НЕ режим файлов)
            if (!message_mode && !file_mode)
            {
                receive_thread = std::thread(receive_frames_codec, tap_fd, sock, &codec);
                std::cout << "🔄 Двунаправленная передача включена (кодек)\n";
            }
        } catch (const std::exception &e) {
            std::cerr << "❌ Ошибка инициализации кодека: " << e.what() << "\n";
            return 1;
        }
    }

    if (file_mode)
    {
        // Режим передачи файлов
        if (use_codec)
        {
            if (!send_file_codec(sock, dest_addr, &codec, file_path)) {
                std::cerr << "❌ Ошибка при отправке файла через кодек\n";
                close(sock);
                return 1;
            }
        }
        else
        {
            if (!send_file_libsodium(sock, dest_addr, tx_key, file_path)) {
                std::cerr << "❌ Ошибка при отправке файла через libsodium\n";
                close(sock);
                return 1;
            }
        }
    }
    else if (message_mode)
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

    if (tap_fd >= 0) {
        close(tap_fd);
    }
    close(sock);
    return 0;
}
