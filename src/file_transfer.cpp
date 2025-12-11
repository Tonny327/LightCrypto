#include "file_transfer.h"
#include "digital_codec.h"
#include <fstream>
#include <cstring>
#include <iostream>
#include <iomanip>
#include <sodium.h>

namespace filetransfer {

// Таблица CRC32 (полином IEEE 802.3)
static uint32_t crc32_table[256];
static bool crc32_table_initialized = false;

void init_crc32_table() {
    if (crc32_table_initialized) return;
    
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t crc = i;
        for (int j = 0; j < 8; j++) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0xEDB88320;
            } else {
                crc >>= 1;
            }
        }
        crc32_table[i] = crc;
    }
    crc32_table_initialized = true;
}

uint32_t crc32(const uint8_t* data, size_t length) {
    init_crc32_table();
    
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < length; i++) {
        uint8_t index = (crc ^ data[i]) & 0xFF;
        crc = (crc >> 8) ^ crc32_table[index];
    }
    return ~crc;
}

void compute_file_hash(const std::vector<uint8_t>& file_data, uint8_t hash[32]) {
    crypto_hash_sha256(hash, file_data.data(), file_data.size());
}

std::vector<uint8_t> serialize_file_header(const FileHeader& header, const std::string& filename) {
    std::vector<uint8_t> result;
    size_t total_size = sizeof(FileHeader) + filename.size();
    result.reserve(total_size);
    
    // Копируем структуру заголовка
    const uint8_t* header_bytes = reinterpret_cast<const uint8_t*>(&header);
    result.insert(result.end(), header_bytes, header_bytes + sizeof(FileHeader));
    
    // Добавляем имя файла
    result.insert(result.end(), filename.begin(), filename.end());
    
    return result;
}

bool deserialize_file_header(const uint8_t* data, size_t size, FileHeader& header, std::string& filename) {
    if (size < sizeof(FileHeader)) {
        return false;
    }
    
    // Копируем структуру заголовка
    std::memcpy(&header, data, sizeof(FileHeader));
    
    // Проверяем магическое число
    if (header.magic != MAGIC_FILE_HEADER) {
        return false;
    }
    
    // Проверяем длину имени файла
    if (size < sizeof(FileHeader) + header.filename_len) {
        return false;
    }
    
    // Извлекаем имя файла
    filename.assign(reinterpret_cast<const char*>(data + sizeof(FileHeader)), header.filename_len);
    
    return true;
}

std::vector<uint8_t> serialize_chunk(const ChunkHeader& header, const uint8_t* data) {
    std::vector<uint8_t> result;
    size_t total_size = sizeof(ChunkHeader) + header.data_size;
    result.reserve(total_size);
    
    // Копируем заголовок чанка
    const uint8_t* header_bytes = reinterpret_cast<const uint8_t*>(&header);
    result.insert(result.end(), header_bytes, header_bytes + sizeof(ChunkHeader));
    
    // Добавляем данные
    result.insert(result.end(), data, data + header.data_size);
    
    return result;
}

bool deserialize_chunk(const uint8_t* data, size_t size, ChunkHeader& header, std::vector<uint8_t>& chunk_data) {
    if (size < sizeof(ChunkHeader)) {
        return false;
    }
    
    // Копируем заголовок
    std::memcpy(&header, data, sizeof(ChunkHeader));
    
    // Проверяем магическое число
    if (header.magic != MAGIC_FILE_CHUNK) {
        return false;
    }
    
    // Проверяем размер данных
    if (size < sizeof(ChunkHeader) + header.data_size) {
        return false;
    }
    
    // Извлекаем данные чанка
    chunk_data.assign(data + sizeof(ChunkHeader), data + sizeof(ChunkHeader) + header.data_size);
    
    // Проверяем контрольную сумму
    uint32_t actual_crc = crc32(chunk_data.data(), chunk_data.size());
    if (actual_crc != header.crc32) {
        std::cerr << "⚠️  CRC32 не совпадает для чанка " << header.chunk_index << "\n";
        return false;
    }
    
    return true;
}

std::vector<uint8_t> serialize_ack(const ChunkAck& ack) {
    std::vector<uint8_t> result;
    const uint8_t* ack_bytes = reinterpret_cast<const uint8_t*>(&ack);
    result.insert(result.end(), ack_bytes, ack_bytes + sizeof(ChunkAck));
    return result;
}

bool deserialize_ack(const uint8_t* data, size_t size, ChunkAck& ack) {
    if (size < sizeof(ChunkAck)) {
        return false;
    }
    
    std::memcpy(&ack, data, sizeof(ChunkAck));
    
    if (ack.magic != MAGIC_FILE_ACK) {
        return false;
    }
    
    return true;
}

std::vector<uint8_t> serialize_sync_request(const SyncRequest& request) {
    std::vector<uint8_t> result;
    const uint8_t* request_bytes = reinterpret_cast<const uint8_t*>(&request);
    result.insert(result.end(), request_bytes, request_bytes + sizeof(SyncRequest));
    return result;
}

bool deserialize_sync_request(const uint8_t* data, size_t size, SyncRequest& request) {
    if (size < sizeof(SyncRequest)) {
        return false;
    }
    
    std::memcpy(&request, data, sizeof(SyncRequest));
    
    if (request.magic != MAGIC_SYNC_REQUEST) {
        return false;
    }
    
    return true;
}

// FileSender implementation
bool FileSender::load_file(const std::string& filepath) {
    // Открываем файл
    std::ifstream file(filepath, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        std::cerr << "❌ Не удалось открыть файл: " << filepath << "\n";
        return false;
    }
    
    // Получаем размер файла
    std::streamsize file_size = file.tellg();
    file.seekg(0, std::ios::beg);
    
    // Читаем весь файл в память
    file_data_.resize(file_size);
    if (!file.read(reinterpret_cast<char*>(file_data_.data()), file_size)) {
        std::cerr << "❌ Ошибка при чтении файла\n";
        return false;
    }
    
    file.close();
    
    // Извлекаем имя файла из пути
    size_t pos = filepath.find_last_of("/\\");
    filename_ = (pos == std::string::npos) ? filepath : filepath.substr(pos + 1);
    
    // Заполняем заголовок
    header_.magic = MAGIC_FILE_HEADER;
    header_.file_size = file_data_.size();
    header_.chunk_size = CHUNK_DATA_SIZE;
    header_.total_chunks = (file_data_.size() + CHUNK_DATA_SIZE - 1) / CHUNK_DATA_SIZE;
    header_.filename_len = filename_.size();
    
    // Вычисляем хеш файла
    compute_file_hash(file_data_, header_.file_hash);
    
    std::cout << "📁 Файл загружен: " << filename_ << " (" << file_size << " байт, " 
              << header_.total_chunks << " чанков)\n";
    
    return true;
}

bool FileSender::get_chunk(uint32_t index, ChunkHeader& chunk_header, std::vector<uint8_t>& chunk_data) {
    if (index >= header_.total_chunks) {
        return false;
    }
    
    // Вычисляем начало и конец чанка
    size_t start_pos = index * CHUNK_DATA_SIZE;
    size_t end_pos = std::min(start_pos + CHUNK_DATA_SIZE, file_data_.size());
    size_t chunk_size = end_pos - start_pos;
    
    // Заполняем заголовок чанка
    chunk_header.magic = MAGIC_FILE_CHUNK;
    chunk_header.chunk_index = index;
    chunk_header.total_chunks = header_.total_chunks;
    chunk_header.data_size = chunk_size;
    
    // Копируем данные чанка
    chunk_data.assign(file_data_.begin() + start_pos, file_data_.begin() + end_pos);
    
    // Вычисляем CRC32
    chunk_header.crc32 = crc32(chunk_data.data(), chunk_data.size());
    
    return true;
}

// FileReceiver implementation
bool FileReceiver::initialize(const FileHeader& header, const std::string& filename) {
    header_ = header;
    filename_ = filename;
    received_count_ = 0;
    
    // Инициализируем буферы для чанков
    received_chunks_.resize(header.total_chunks, false);
    chunk_buffers_.resize(header.total_chunks);
    
    std::cout << "📥 Инициализирован прием файла: " << filename_ << " (" 
              << header_.file_size << " байт, " << header_.total_chunks << " чанков)\n";
    
    return true;
}

bool FileReceiver::add_chunk(const ChunkHeader& chunk_header, const std::vector<uint8_t>& chunk_data) {
    // Проверяем индекс чанка
    if (chunk_header.chunk_index >= header_.total_chunks) {
        std::cerr << "❌ Неверный индекс чанка: " << chunk_header.chunk_index << "\n";
        return false;
    }
    
    // Проверяем, не был ли этот чанк уже получен
    if (received_chunks_[chunk_header.chunk_index]) {
        std::cout << "⚠️  Чанк " << chunk_header.chunk_index << " уже был получен, пропускаем\n";
        return true;
    }
    
    // Сохраняем чанк
    chunk_buffers_[chunk_header.chunk_index] = chunk_data;
    received_chunks_[chunk_header.chunk_index] = true;
    received_count_++;
    
    std::cout << "✅ Получен чанк " << chunk_header.chunk_index + 1 << "/" 
              << header_.total_chunks << " (" << chunk_header.data_size << " байт, "
              << std::fixed << std::setprecision(1) << get_progress() << "%)\n";
    
    return true;
}

bool FileReceiver::is_complete() const {
    return received_count_ == header_.total_chunks;
}

float FileReceiver::get_progress() const {
    if (header_.total_chunks == 0) return 0.0f;
    return (100.0f * received_count_) / header_.total_chunks;
}

bool FileReceiver::save_file(const std::string& output_path) {
    if (!is_complete()) {
        std::cerr << "❌ Не все чанки получены (" << received_count_ << "/" 
                  << header_.total_chunks << ")\n";
        return false;
    }
    
    // Собираем файл из чанков
    std::vector<uint8_t> file_data;
    file_data.reserve(header_.file_size);
    
    for (uint32_t i = 0; i < header_.total_chunks; i++) {
        file_data.insert(file_data.end(), chunk_buffers_[i].begin(), chunk_buffers_[i].end());
    }
    
    // Проверяем размер
    if (file_data.size() != header_.file_size) {
        std::cerr << "❌ Размер собранного файла не совпадает с ожидаемым: " 
                  << file_data.size() << " != " << header_.file_size << "\n";
        return false;
    }
    
    // Проверяем хеш
    uint8_t actual_hash[32];
    compute_file_hash(file_data, actual_hash);
    
    if (std::memcmp(actual_hash, header_.file_hash, 32) != 0) {
        std::cerr << "❌ Хеш файла не совпадает - файл поврежден!\n";
        return false;
    }
    
    // Сохраняем файл
    std::ofstream out_file(output_path, std::ios::binary);
    if (!out_file.is_open()) {
        std::cerr << "❌ Не удалось создать выходной файл: " << output_path << "\n";
        return false;
    }
    
    out_file.write(reinterpret_cast<const char*>(file_data.data()), file_data.size());
    out_file.close();
    
    std::cout << "✅ Файл успешно сохранен: " << output_path << "\n";
    std::cout << "✅ Проверка целостности пройдена!\n";
    
    return true;
}

bool FileReceiver::verify_integrity() const {
    if (!is_complete()) {
        return false;
    }
    
    // Собираем данные для проверки
    std::vector<uint8_t> file_data;
    file_data.reserve(header_.file_size);
    
    for (uint32_t i = 0; i < header_.total_chunks; i++) {
        file_data.insert(file_data.end(), chunk_buffers_[i].begin(), chunk_buffers_[i].end());
    }
    
    // Проверяем хеш
    uint8_t actual_hash[32];
    compute_file_hash(file_data, actual_hash);
    
    return std::memcmp(actual_hash, header_.file_hash, 32) == 0;
}

std::vector<uint32_t> FileReceiver::get_missing_chunks() const {
    std::vector<uint32_t> missing;
    for (uint32_t i = 0; i < header_.total_chunks; i++) {
        if (!received_chunks_[i]) {
            missing.push_back(i);
        }
    }
    return missing;
}

// Локальное кодирование файла в контейнер
bool encode_file_to_container(const std::string& input_path, 
                              const std::string& output_path, 
                              digitalcodec::DigitalCodec& codec) {
    std::cout << "📁 Начинаем локальное кодирование файла: " << input_path << "\n";
    
    // Загружаем файл
    FileSender sender;
    if (!sender.load_file(input_path)) {
        std::cerr << "❌ Ошибка загрузки файла\n";
        return false;
    }
    
    // Сбрасываем состояния кодека перед началом кодирования
    codec.reset();
    
    // Открываем выходной файл для записи
    std::ofstream out_file(output_path, std::ios::binary);
    if (!out_file.is_open()) {
        std::cerr << "❌ Не удалось создать выходной файл: " << output_path << "\n";
        return false;
    }
    
    // 1. Кодируем и записываем заголовок файла
    auto header_bytes = serialize_file_header(sender.get_header(), sender.get_filename());
    std::vector<uint8_t> framed_header = codec.encodeMessage(header_bytes);
    
    // Записываем фрейм заголовка: [2 байта длины фрейма] + [данные фрейма]
    // encodeMessage уже добавляет 2 байта длины payload в начале, но нам нужна длина всего фрейма
    uint16_t frame_len = static_cast<uint16_t>(framed_header.size());
    uint8_t len_bytes[2] = {static_cast<uint8_t>(frame_len & 0xFF), static_cast<uint8_t>((frame_len >> 8) & 0xFF)};
    out_file.write(reinterpret_cast<const char*>(len_bytes), 2);
    out_file.write(reinterpret_cast<const char*>(framed_header.data()), framed_header.size());
    
    if (!out_file.good()) {
        std::cerr << "❌ Ошибка записи заголовка в файл\n";
        out_file.close();
        return false;
    }
    
    std::cout << "✅ Заголовок файла закодирован и записан (" << framed_header.size() << " байт)\n";
    
    // 2. Кодируем и записываем чанки
    uint32_t total_chunks = sender.get_total_chunks();
    for (uint32_t i = 0; i < total_chunks; i++) {
        ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (!sender.get_chunk(i, chunk_header, chunk_data)) {
            std::cerr << "❌ Ошибка получения чанка " << i << "\n";
            out_file.close();
            return false;
        }
        
        // Сериализуем чанк
        auto chunk_bytes = serialize_chunk(chunk_header, chunk_data.data());
        
        // Кодируем чанк (состояния эволюционируют между чанками)
        std::vector<uint8_t> framed_chunk = codec.encodeMessage(chunk_bytes);
        
        // Записываем фрейм чанка: [2 байта длины фрейма] + [данные фрейма]
        uint16_t frame_len = static_cast<uint16_t>(framed_chunk.size());
        uint8_t len_bytes[2] = {static_cast<uint8_t>(frame_len & 0xFF), static_cast<uint8_t>((frame_len >> 8) & 0xFF)};
        out_file.write(reinterpret_cast<const char*>(len_bytes), 2);
        out_file.write(reinterpret_cast<const char*>(framed_chunk.data()), framed_chunk.size());
        
        if (!out_file.good()) {
            std::cerr << "❌ Ошибка записи чанка " << i << " в файл\n";
            out_file.close();
            return false;
        }
        
        // Показываем прогресс
        float progress = (100.0f * (i + 1)) / total_chunks;
        std::cout << "📤 Закодирован чанк " << (i + 1) << "/" << total_chunks 
                  << " (" << chunk_header.data_size << " байт, "
                  << std::fixed << std::setprecision(1) << progress << "%)\n";
    }
    
    out_file.close();
    
    std::cout << "✅ Файл успешно закодирован в контейнер: " << output_path << "\n";
    std::cout << "📊 Размер исходного файла: " << sender.get_header().file_size << " байт\n";
    std::cout << "📊 Количество чанков: " << total_chunks << "\n";
    
    return true;
}

// Локальное декодирование контейнера в файл
bool decode_container_to_file(const std::string& container_path, 
                               const std::string& output_path, 
                               digitalcodec::DigitalCodec& codec) {
    std::cout << "📥 Начинаем локальное декодирование контейнера: " << container_path << "\n";
    
    // Открываем контейнер для чтения
    std::ifstream in_file(container_path, std::ios::binary);
    if (!in_file.is_open()) {
        std::cerr << "❌ Не удалось открыть контейнер: " << container_path << "\n";
        return false;
    }
    
    // Сбрасываем состояния кодека перед началом декодирования
    codec.reset();
    
    FileReceiver receiver;
    bool header_received = false;
    std::string filename;
    
    // Читаем фреймы последовательно
    while (true) {
        // Читаем 2 байта длины фрейма (little-endian)
        uint8_t len_bytes[2];
        in_file.read(reinterpret_cast<char*>(len_bytes), 2);
        
        if (in_file.eof() || in_file.gcount() != 2) {
            // Достигли конца файла
            break;
        }
        
        // Получаем длину фрейма
        uint16_t frame_len = len_bytes[0] | (len_bytes[1] << 8);
        
        if (frame_len == 0 || frame_len > 65535) {
            std::cerr << "❌ Неверная длина фрейма: " << frame_len << "\n";
            in_file.close();
            return false;
        }
        
        // Читаем кодированные данные фрейма (frame_len - это длина всего фрейма включая 2 байта длины payload)
        std::vector<uint8_t> framed_data(frame_len);
        in_file.read(reinterpret_cast<char*>(framed_data.data()), frame_len);
        
        if (in_file.gcount() != frame_len) {
            std::cerr << "❌ Не удалось прочитать полный фрейм (прочитано " 
                      << in_file.gcount() << " из " << frame_len << " байт)\n";
            in_file.close();
            return false;
        }
        
        // Декодируем фрейм (framed_data содержит весь фрейм с 2 байтами длины payload в начале)
        // decodeMessage ожидает фрейм в формате [2 байта длины payload] + [кодированные данные]
        std::vector<uint8_t> decoded_bytes = codec.decodeMessage(framed_data, 0);
        
        if (decoded_bytes.empty()) {
            std::cerr << "❌ Ошибка декодирования фрейма\n";
            in_file.close();
            return false;
        }
        
        // Проверяем, это заголовок или чанк
        if (!header_received) {
            // Пытаемся распарсить как заголовок файла
            FileHeader header;
            if (deserialize_file_header(decoded_bytes.data(), decoded_bytes.size(), header, filename)) {
                std::cout << "📥 Получен заголовок файла: " << filename << "\n";
                receiver.initialize(header, filename);
                header_received = true;
                continue;
            } else {
                std::cerr << "❌ Не удалось распарсить заголовок файла\n";
                in_file.close();
                return false;
            }
        }
        
        // Пытаемся распарсить как чанк
        ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (deserialize_chunk(decoded_bytes.data(), decoded_bytes.size(), chunk_header, chunk_data)) {
            // Добавляем чанк (CRC32 проверяется внутри deserialize_chunk)
            if (!receiver.add_chunk(chunk_header, chunk_data)) {
                std::cerr << "⚠️  Ошибка добавления чанка " << chunk_header.chunk_index << "\n";
            }
            
            // Проверяем, все ли чанки получены
            if (receiver.is_complete()) {
                std::cout << "✅ Все чанки получены, сохраняем файл...\n";
                
                // Формируем путь для сохранения
                std::string save_path = output_path;
                if (save_path.empty() || save_path == "./received_file") {
                    save_path = "./" + filename;
                }
                
                if (receiver.save_file(save_path)) {
                    // Проверяем целостность
                    if (receiver.verify_integrity()) {
                        std::cout << "✅ Проверка целостности пройдена!\n";
                    } else {
                        std::cerr << "⚠️  Проверка целостности не пройдена!\n";
                        in_file.close();
                        return false;
                    }
                    
                    in_file.close();
                    return true;
                } else {
                    std::cerr << "❌ Ошибка при сохранении файла\n";
                    in_file.close();
                    return false;
                }
            }
        } else {
            std::cerr << "⚠️  Не удалось распарсить фрейм как чанк (размер: " 
                      << decoded_bytes.size() << " байт)\n";
            // Продолжаем чтение, возможно это следующий фрейм
        }
    }
    
    in_file.close();
    
    if (!header_received) {
        std::cerr << "❌ Заголовок файла не был получен\n";
        return false;
    }
    
    if (!receiver.is_complete()) {
        std::cerr << "❌ Не все чанки получены (" << receiver.get_received_count() 
                  << "/" << receiver.get_total_chunks() << ")\n";
        return false;
    }
    
    return true;
}

} // namespace filetransfer
