#include "file_transfer.h"
#include "digital_codec.h"
#include <fstream>
#include <cstring>
#include <iostream>
#include <iomanip>
#include <sodium.h>
#include <algorithm>
#include <map>
#include <sstream>

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
    // Константы маркеров (оптимизированы для 47-байтного чанка)
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;  // Уменьшено с 8 до 4 байт для экономии места
    
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
        
        // Вычисляем CRC32 зашифрованных данных
        uint32_t framed_crc = crc32(framed_chunk.data(), framed_chunk.size());
        
        // Записываем маркер начала
        out_file.write(reinterpret_cast<const char*>(START_MARKER), MARKER_SIZE);
        
        // Записываем номер чанка (4 байта, little-endian)
        uint32_t chunk_num = i;
        uint8_t chunk_num_bytes[4] = {
            static_cast<uint8_t>(chunk_num & 0xFF),
            static_cast<uint8_t>((chunk_num >> 8) & 0xFF),
            static_cast<uint8_t>((chunk_num >> 16) & 0xFF),
            static_cast<uint8_t>((chunk_num >> 24) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(chunk_num_bytes), 4);
        
        // Записываем длину зашифрованных данных (4 байта, little-endian)
        uint32_t framed_len = static_cast<uint32_t>(framed_chunk.size());
        uint8_t len_bytes[4] = {
            static_cast<uint8_t>(framed_len & 0xFF),
            static_cast<uint8_t>((framed_len >> 8) & 0xFF),
            static_cast<uint8_t>((framed_len >> 16) & 0xFF),
            static_cast<uint8_t>((framed_len >> 24) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(len_bytes), 4);
        
        // Записываем CRC32 зашифрованных данных (4 байта, little-endian)
        uint8_t crc_bytes[4] = {
            static_cast<uint8_t>(framed_crc & 0xFF),
            static_cast<uint8_t>((framed_crc >> 8) & 0xFF),
            static_cast<uint8_t>((framed_crc >> 16) & 0xFF),
            static_cast<uint8_t>((framed_crc >> 24) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(crc_bytes), 4);
        
        // Записываем зашифрованные данные
        out_file.write(reinterpret_cast<const char*>(framed_chunk.data()), framed_chunk.size());
        
        // Записываем маркер конца
        out_file.write(reinterpret_cast<const char*>(END_MARKER), MARKER_SIZE);
        
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
    
    // Константы маркеров (оптимизированы для 47-байтного чанка)
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;  // Уменьшено с 8 до 4 байт для экономии места
    const size_t MAX_PACKET_SIZE = 16000;
    
    FileReceiver receiver;
    bool header_received = false;
    std::string filename;
    
    // Читаем весь файл в буфер
    in_file.seekg(0, std::ios::end);
    size_t file_size = in_file.tellg();
    in_file.seekg(0, std::ios::beg);
    
    std::vector<uint8_t> file_buffer(file_size);
    in_file.read(reinterpret_cast<char*>(file_buffer.data()), file_size);
    in_file.close();
    
    // Обрабатываем заголовок файла (первые фреймы до появления маркеров)
    // Заголовок имеет старый формат: [2 байта длины] + [данные]
    // Но после передачи через радиоканал в начале файла может быть шум,
    // поэтому сначала ищем маркер первого чанка, а затем ищем заголовок перед ним
    
    size_t pos = 0;
    
    // Сначала ищем маркер начала первого чанка
    auto first_chunk_pos = std::search(
        file_buffer.begin(),
        file_buffer.end(),
        START_MARKER,
        START_MARKER + MARKER_SIZE
    );
    
    if (first_chunk_pos == file_buffer.end()) {
        std::cerr << "❌ Не найден маркер начала чанка в файле\n";
        return false;
    }
    
    size_t first_chunk_offset = std::distance(file_buffer.begin(), first_chunk_pos);
    std::cout << "🔍 Найден первый чанк на позиции: " << first_chunk_offset << " байт\n";
    
    // Теперь пробуем найти заголовок перед первым чанком
    // Пробуем декодировать с разных позиций перед чанком
    bool header_found = false;
    size_t header_start = 0;
    size_t header_len = 0;
    
    // Пробуем с начала файла и до первого чанка (с шагом для ускорения)
    // Но сначала пробуем стандартный формат (первые 2 байта)
    if (first_chunk_offset >= 2) {
        codec.reset(); // Сбрасываем кодек перед попыткой
        uint16_t frame_len = file_buffer[0] | (file_buffer[1] << 8);
        if (frame_len > 0 && frame_len <= MAX_PACKET_SIZE && 
            2 + frame_len <= first_chunk_offset) {
            std::vector<uint8_t> framed_header(
                file_buffer.begin() + 2,
                file_buffer.begin() + 2 + frame_len
            );
            
            std::vector<uint8_t> decoded_header = codec.decodeMessage(framed_header, 0);
            if (!decoded_header.empty() && decoded_header.size() >= sizeof(FileHeader)) {
                FileHeader* test_header = reinterpret_cast<FileHeader*>(decoded_header.data());
                if (test_header->magic == MAGIC_FILE_HEADER) {
                    header_start = 0;
                    header_len = frame_len;
                    header_found = true;
                    std::cout << "✅ Заголовок найден в стандартной позиции (начало файла)\n";
                }
            }
        }
    }
    
    // Если не нашли в стандартной позиции, пробуем другие позиции
    if (!header_found) {
        std::cout << "🔍 Ищу заголовок перед первым чанком...\n";
        // Пробуем с шагом, чтобы не проверять каждую позицию (ускоряет поиск)
        for (size_t try_pos = 0; try_pos < first_chunk_offset && try_pos + 2 < first_chunk_offset; try_pos += 1) {
            // Читаем 2 байта длины
            uint16_t frame_len = file_buffer[try_pos] | (file_buffer[try_pos + 1] << 8);
            
            // Проверяем разумность длины
            if (frame_len == 0 || frame_len > MAX_PACKET_SIZE || 
                try_pos + 2 + frame_len > first_chunk_offset) {
                continue;
            }
            
            // Извлекаем потенциальный заголовок
            std::vector<uint8_t> framed_header(
                file_buffer.begin() + try_pos + 2,
                file_buffer.begin() + try_pos + 2 + frame_len
            );
            
            // Сбрасываем кодек перед каждой попыткой декодирования
            codec.reset();
            
            // Пробуем декодировать
            std::vector<uint8_t> decoded_header = codec.decodeMessage(framed_header, 0);
            if (decoded_header.empty()) {
                continue;
            }
            
            // Проверяем магическое число
            if (decoded_header.size() >= sizeof(FileHeader)) {
                FileHeader* test_header = reinterpret_cast<FileHeader*>(decoded_header.data());
                if (test_header->magic == MAGIC_FILE_HEADER) {
                    // Нашли правильный заголовок!
                    header_start = try_pos;
                    header_len = frame_len;
                    header_found = true;
                    std::cout << "✅ Заголовок найден на позиции: " << try_pos << " байт (после шума)\n";
                    break;
                }
            }
        }
    }
    
    if (!header_found) {
        std::cerr << "❌ Не удалось найти заголовок файла перед первым чанком\n";
        std::cerr << "   Пробовал позиции от 0 до " << first_chunk_offset << " байт\n";
        return false;
    }
    
    // Декодируем найденный заголовок (сбрасываем кодек для правильного декодирования)
    codec.reset();
    std::vector<uint8_t> framed_header(
        file_buffer.begin() + header_start + 2,
        file_buffer.begin() + header_start + 2 + header_len
    );
    
    std::vector<uint8_t> decoded_header = codec.decodeMessage(framed_header, 0);
    if (decoded_header.empty()) {
        std::cerr << "❌ Ошибка декодирования заголовка\n";
        return false;
    }
    
    FileHeader header;
    if (!deserialize_file_header(decoded_header.data(), decoded_header.size(), header, filename)) {
        std::cerr << "❌ Не удалось распарсить заголовок файла\n";
        return false;
    }
    
    std::cout << "📥 Получен заголовок файла: " << filename << "\n";
    receiver.initialize(header, filename);
    header_received = true;
    
    // Начинаем поиск чанков с позиции после заголовка
    pos = header_start + 2 + header_len;
    
    // Ожидаемый номер следующего чанка
    uint32_t expected_chunk_index = 0;
    uint32_t chunks_found = 0;
    uint32_t chunks_skipped = 0;
    uint32_t chunks_crc_failed = 0;
    
    // Ищем чанки по маркерам в оставшейся части файла
    while (pos < file_buffer.size()) {
        // Ищем маркер начала
        auto start_pos = std::search(
            file_buffer.begin() + pos,
            file_buffer.end(),
            START_MARKER,
            START_MARKER + MARKER_SIZE
        );
        
        if (start_pos == file_buffer.end()) {
            // Маркер не найден, заканчиваем
            break;
        }
        
        size_t chunk_start_pos = std::distance(file_buffer.begin(), start_pos) + MARKER_SIZE;
        pos = chunk_start_pos;
        
        // Проверяем, достаточно ли данных для номера чанка + длины + CRC32
        if (pos + 4 + 4 + 4 > file_buffer.size()) {
            std::cerr << "⚠️  Недостаточно данных для чтения метаданных чанка\n";
            break;
        }
        
        // Читаем номер чанка (4 байта, little-endian)
        uint32_t chunk_index = file_buffer[pos] |
                               (file_buffer[pos + 1] << 8) |
                               (file_buffer[pos + 2] << 16) |
                               (file_buffer[pos + 3] << 24);
        pos += 4;
        
        // Проверяем последовательность номеров (предупреждение, но не критично)
        if (chunk_index != expected_chunk_index) {
            std::cerr << "⚠️  Неожиданный номер чанка: ожидался " << expected_chunk_index
                      << ", получен " << chunk_index << "\n";
            // Продолжаем обработку
        }
        
        // Читаем длину зашифрованных данных (4 байта, little-endian)
        uint32_t framed_len = file_buffer[pos] |
                             (file_buffer[pos + 1] << 8) |
                             (file_buffer[pos + 2] << 16) |
                             (file_buffer[pos + 3] << 24);
        pos += 4;
        
        // Проверяем разумность длины
        if (framed_len == 0 || framed_len > MAX_PACKET_SIZE) {
            std::cerr << "⚠️  Неверная длина чанка " << chunk_index << ": " << framed_len << "\n";
            // Пропускаем повреждённый пакет, продолжаем поиск с позиции после маркера начала минус 1 байт
            pos = chunk_start_pos - 1;
            chunks_skipped++;
            continue;
        }
        
        // Читаем ожидаемый CRC32 (4 байта, little-endian)
        uint32_t expected_crc = file_buffer[pos] |
                               (file_buffer[pos + 1] << 8) |
                               (file_buffer[pos + 2] << 16) |
                               (file_buffer[pos + 3] << 24);
        pos += 4;
        
        // Проверяем, достаточно ли данных для полного пакета
        if (pos + framed_len + MARKER_SIZE > file_buffer.size()) {
            std::cerr << "⚠️  Недостаточно данных для чтения полного чанка " << chunk_index << "\n";
            break;
        }
        
        // Извлекаем зашифрованные данные
        std::vector<uint8_t> framed_data(
            file_buffer.begin() + pos,
            file_buffer.begin() + pos + framed_len
        );
        pos += framed_len;
        
        // Проверяем CRC32 зашифрованных данных
        uint32_t actual_crc = crc32(framed_data.data(), framed_data.size());
        if (actual_crc != expected_crc) {
            std::cerr << "❌ CRC32 не совпадает для чанка " << chunk_index
                      << " (ожидался 0x" << std::hex << expected_crc
                      << ", получен 0x" << actual_crc << std::dec << ")\n";
            // Пропускаем повреждённый пакет, продолжаем поиск с позиции после маркера начала минус 1 байт
            pos = chunk_start_pos - 1;
            chunks_crc_failed++;
            continue;
        }
        
        // Проверяем маркер конца
        if (pos + MARKER_SIZE > file_buffer.size()) {
            std::cerr << "⚠️  Недостаточно данных для чтения маркера конца чанка " << chunk_index << "\n";
            break;
        }
        
        bool end_marker_ok = std::equal(
            END_MARKER,
            END_MARKER + MARKER_SIZE,
            file_buffer.begin() + pos
        );
        
        if (!end_marker_ok) {
            std::cerr << "⚠️  Маркер конца не совпал для чанка " << chunk_index << "\n";
            // Пропускаем повреждённый пакет, продолжаем поиск с позиции после маркера начала минус 1 байт
            pos = chunk_start_pos - 1;
            chunks_skipped++;
            continue;
        }
        
        pos += MARKER_SIZE;
        
        // Декодируем фрейм
        std::vector<uint8_t> decoded_bytes = codec.decodeMessage(framed_data, 0);
        
        if (decoded_bytes.empty()) {
            std::cerr << "❌ Ошибка декодирования фрейма чанка " << chunk_index << "\n";
            continue;
        }
        
        // Парсим чанк
        ChunkHeader chunk_header;
        std::vector<uint8_t> chunk_data;
        
        if (deserialize_chunk(decoded_bytes.data(), decoded_bytes.size(), chunk_header, chunk_data)) {
            // Добавляем чанк (CRC32 данных проверяется внутри deserialize_chunk)
            if (receiver.add_chunk(chunk_header, chunk_data)) {
                chunks_found++;
                expected_chunk_index++;
            } else {
                std::cerr << "⚠️  Ошибка добавления чанка " << chunk_header.chunk_index << "\n";
            }
            
            // Проверяем, все ли чанки получены
            if (receiver.is_complete()) {
                std::cout << "✅ Все чанки получены, сохраняем файл...\n";
                std::cout << "📊 Статистика: найдено " << chunks_found << " чанков, "
                          << "пропущено " << chunks_skipped << ", "
                          << "CRC32 ошибок " << chunks_crc_failed << "\n";
                
                // Формируем путь для сохранения
                std::string save_path = output_path;
                if (save_path.empty() || save_path == "./received_file") {
                    save_path = "./" + filename;
                }
                
                if (receiver.save_file(save_path)) {
                    if (receiver.verify_integrity()) {
                        std::cout << "✅ Проверка целостности пройдена!\n";
                        return true;
                    } else {
                        std::cerr << "⚠️  Проверка целостности не пройдена!\n";
                        return false;
                    }
                } else {
                    std::cerr << "❌ Ошибка при сохранении файла\n";
                    return false;
                }
            }
        } else {
            std::cerr << "⚠️  Не удалось распарсить фрейм как чанк " << chunk_index << "\n";
        }
    }
    
    // Финальная проверка
    if (!header_received) {
        std::cerr << "❌ Заголовок файла не был получен\n";
        return false;
    }
    
    if (!receiver.is_complete()) {
        std::cerr << "❌ Не все чанки получены (" << receiver.get_received_count()
                  << "/" << receiver.get_total_chunks() << ")\n";
        std::cerr << "📊 Статистика: найдено " << chunks_found << " чанков, "
                  << "пропущено " << chunks_skipped << ", "
                  << "CRC32 ошибок " << chunks_crc_failed << "\n";
        return false;
    }
    
    return true;
}

// Локальное кодирование файла в контейнер БЕЗ шифрования (только маркеры и CRC32)
// Разбивает текст на чанки фиксированного размера для лучшей устойчивости к шуму
bool encode_file_to_container_plain(const std::string& input_path, 
                                    const std::string& output_path) {
    std::cout << "📁 Начинаем локальное кодирование файла (без шифрования): " << input_path << "\n";
    
    // Размер чанка (можно настроить)
    // Ограничение: весь чанк (маркеры + метаданные + данные) должен быть <= 47 байт
    // Структура: START_MARKER(4) + chunk_num(2) + total_chunks(2) + CRC32(4) + данные(31) + END_MARKER(4) = 47 байт
    const size_t CHUNK_SIZE = 31;  // 31 байт данных на чанк (максимум для радиочастотного канала)
    
    // Открываем входной файл
    std::ifstream in_file(input_path, std::ios::binary);
    if (!in_file.is_open()) {
        std::cerr << "❌ Не удалось открыть файл: " << input_path << "\n";
        return false;
    }
    
    // Читаем весь файл
    std::string file_content((std::istreambuf_iterator<char>(in_file)),
                            std::istreambuf_iterator<char>());
    in_file.close();
    
    if (file_content.empty()) {
        std::cerr << "❌ Файл пуст\n";
        return false;
    }
    
    // Разбиваем на чанки фиксированного размера
    std::vector<std::string> chunks;
    for (size_t i = 0; i < file_content.length(); i += CHUNK_SIZE) {
        size_t chunk_len = std::min(CHUNK_SIZE, file_content.length() - i);
        chunks.push_back(file_content.substr(i, chunk_len));
    }
    
    if (chunks.empty()) {
        std::cerr << "❌ Не удалось создать чанки\n";
        return false;
    }
    
    std::cout << "📊 Размер файла: " << file_content.length() << " байт\n";
    std::cout << "📊 Создано чанков: " << chunks.size() << " (по " << CHUNK_SIZE << " символов)\n";
    
    // Открываем выходной файл
    std::ofstream out_file(output_path, std::ios::binary);
    if (!out_file.is_open()) {
        std::cerr << "❌ Не удалось создать выходной файл: " << output_path << "\n";
        return false;
    }
    
    // Константы маркеров (оптимизированы для 47-байтного чанка)
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;  // Уменьшено с 8 до 4 байт для экономии места
    
    // Записываем каждый чанк с маркерами (без заголовка - вся информация в чанках)
    for (uint32_t i = 0; i < chunks.size(); i++) {
        const std::string& chunk = chunks[i];
        std::vector<uint8_t> chunk_bytes(chunk.begin(), chunk.end());
        
        // Дополняем чанк нулями до фиксированного размера (31 байт) для 47-байтного чанка
        // Это необходимо для радиочастотного канала с ограничением в 47 байт
        if (chunk_bytes.size() < CHUNK_SIZE) {
            chunk_bytes.resize(CHUNK_SIZE, 0);  // Дополняем нулями
        }
        
        // Вычисляем CRC32 чанка (всегда для 31 байта)
        uint32_t chunk_crc = crc32(chunk_bytes.data(), chunk_bytes.size());
        
        // Записываем маркер начала (4 байта)
        out_file.write(reinterpret_cast<const char*>(START_MARKER), MARKER_SIZE);
        
        // Записываем номер чанка (2 байта, uint16_t, little-endian) - оптимизация для 47-байтного чанка
        uint16_t chunk_num = static_cast<uint16_t>(i);
        uint8_t chunk_num_bytes[2] = {
            static_cast<uint8_t>(chunk_num & 0xFF),
            static_cast<uint8_t>((chunk_num >> 8) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(chunk_num_bytes), 2);
        
        // Записываем общее количество чанков (2 байта, uint16_t, little-endian) - для избыточности
        uint16_t total_chunks = static_cast<uint16_t>(chunks.size());
        uint8_t total_chunks_bytes[2] = {
            static_cast<uint8_t>(total_chunks & 0xFF),
            static_cast<uint8_t>((total_chunks >> 8) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(total_chunks_bytes), 2);
        
        // Записываем CRC32 чанка (4 байта, little-endian)
        uint8_t crc_bytes[4] = {
            static_cast<uint8_t>(chunk_crc & 0xFF),
            static_cast<uint8_t>((chunk_crc >> 8) & 0xFF),
            static_cast<uint8_t>((chunk_crc >> 16) & 0xFF),
            static_cast<uint8_t>((chunk_crc >> 24) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(crc_bytes), 4);
        
        // Записываем сам чанк (до 31 байта)
        out_file.write(reinterpret_cast<const char*>(chunk_bytes.data()), chunk_bytes.size());
        
        // Записываем маркер конца
        out_file.write(reinterpret_cast<const char*>(END_MARKER), MARKER_SIZE);
        
        if (!out_file.good()) {
            std::cerr << "❌ Ошибка записи чанка " << i << "\n";
            out_file.close();
            return false;
        }
        
        if ((i + 1) % 10 == 0 || i == chunks.size() - 1) {
            std::cout << "📤 Записано чанков: " << (i + 1) << "/" << chunks.size() << "\n";
        }
    }
    
    out_file.close();
    
    std::cout << "✅ Файл успешно закодирован в контейнер (без шифрования): " << output_path << "\n";
    std::cout << "📊 Количество чанков: " << chunks.size() << "\n";
    
    return true;
}

// Структура для результата поиска чанка по номеру
struct ChunkSearchResult {
    bool found;
    std::string data;
    size_t position;
};

// Функция для целенаправленного поиска конкретного чанка по его номеру
static ChunkSearchResult find_chunk_by_number(
    const std::vector<uint8_t>& file_buffer,
    uint16_t target_chunk_num,
    size_t start_pos = 0
) {
    ChunkSearchResult result = {false, "", 0};
    
    // Константы маркеров (должны совпадать с используемыми в decode_container_to_file_plain)
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;
    const size_t CHUNK_DATA_SIZE = 31;
    const size_t FULL_CHUNK_SIZE = MARKER_SIZE + 2 + 2 + 4 + CHUNK_DATA_SIZE + MARKER_SIZE;  // 47 байт
    
    // Ищем все маркеры START_MARKER начиная с start_pos
    size_t pos = start_pos;
    while (pos < file_buffer.size()) {
        auto marker_pos = std::search(
            file_buffer.begin() + pos,
            file_buffer.end(),
            START_MARKER,
            START_MARKER + MARKER_SIZE
        );
        
        if (marker_pos == file_buffer.end()) {
            break;  // Больше маркеров не найдено
        }
        
        size_t chunk_start = std::distance(file_buffer.begin(), marker_pos) + MARKER_SIZE;
        
        // Проверяем достаточность данных для полного чанка
        if (chunk_start + FULL_CHUNK_SIZE - MARKER_SIZE > file_buffer.size()) {
            pos = chunk_start;
            continue;
        }
        
        // Читаем номер чанка (2 байта, uint16_t, little-endian)
        uint16_t chunk_num = file_buffer[chunk_start] | 
                            (file_buffer[chunk_start + 1] << 8);
        
        // Если номер совпадает с искомым - проверяем валидность
        if (chunk_num == target_chunk_num) {
            size_t data_pos = chunk_start;
            
            // Пропускаем total_chunks (2 байта)
            data_pos += 2;
            
            // Читаем ожидаемый CRC32 (4 байта)
            uint32_t expected_crc = file_buffer[data_pos] |
                                   (file_buffer[data_pos + 1] << 8) |
                                   (file_buffer[data_pos + 2] << 16) |
                                   (file_buffer[data_pos + 3] << 24);
            data_pos += 4;
            
            // Проверяем достаточность данных
            if (data_pos + CHUNK_DATA_SIZE + MARKER_SIZE > file_buffer.size()) {
                pos = chunk_start + 1;
                continue;
            }
            
            // Извлекаем данные чанка
            std::vector<uint8_t> chunk_bytes(
                file_buffer.begin() + data_pos,
                file_buffer.begin() + data_pos + CHUNK_DATA_SIZE
            );
            data_pos += CHUNK_DATA_SIZE;
            
            // Проверяем CRC32
            uint32_t actual_crc = crc32(chunk_bytes.data(), chunk_bytes.size());
            if (actual_crc != expected_crc) {
                pos = chunk_start + 1;
                continue;  // CRC32 не совпадает, продолжаем поиск
            }
            
            // Проверяем маркер конца
            if (data_pos + MARKER_SIZE > file_buffer.size()) {
                pos = chunk_start + 1;
                continue;
            }
            
            bool end_marker_ok = std::equal(
                END_MARKER,
                END_MARKER + MARKER_SIZE,
                file_buffer.begin() + data_pos
            );
            
            if (!end_marker_ok) {
                pos = chunk_start + 1;
                continue;  // END_MARKER не совпадает, продолжаем поиск
            }
            
            // Чанк валиден! Возвращаем результат
            result.found = true;
            result.data = std::string(chunk_bytes.begin(), chunk_bytes.end());
            result.position = std::distance(file_buffer.begin(), marker_pos);
            return result;
        }
        
        // Номер не совпадает - продолжаем поиск
        pos = chunk_start + 1;
    }
    
    return result;  // Чанк не найден
}

// Локальное декодирование контейнера в файл БЕЗ шифрования (поиск по маркерам и CRC32)
// Собирает чанки фиксированного размера обратно в исходный текст
bool decode_container_to_file_plain(const std::string& container_path, 
                                    const std::string& output_path) {
    std::cout << "📥 Начинаем локальное декодирование контейнера (без шифрования): " << container_path << "\n";
    
    // Открываем контейнер
    std::ifstream in_file(container_path, std::ios::binary);
    if (!in_file.is_open()) {
        std::cerr << "❌ Не удалось открыть контейнер: " << container_path << "\n";
        return false;
    }
    
    // Константы маркеров
    // Константы маркеров (оптимизированы для 47-байтного чанка)
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;  // Уменьшено с 8 до 4 байт для экономии места
    const size_t CHUNK_DATA_SIZE = 31;  // Фиксированный размер данных в чанке (для 47-байтного чанка)
    const size_t MAX_CHUNK_SIZE = CHUNK_DATA_SIZE;  // Максимальный размер данных чанка
    
    // Читаем весь файл в буфер
    in_file.seekg(0, std::ios::end);
    size_t file_size = in_file.tellg();
    in_file.seekg(0, std::ios::beg);
    
    std::vector<uint8_t> file_buffer(file_size);
    in_file.read(reinterpret_cast<char*>(file_buffer.data()), file_size);
    in_file.close();
    
    std::cout << "📊 Размер файла: " << file_size << " байт\n";
    
    // Ищем первый маркер начала чанка
    auto first_marker_pos = std::search(
        file_buffer.begin(),
        file_buffer.end(),
        START_MARKER,
        START_MARKER + MARKER_SIZE
    );
    
    if (first_marker_pos == file_buffer.end()) {
        std::cerr << "❌ Маркеры начала не найдены в файле!\n";
        std::cerr << "   Возможные причины:\n";
        std::cerr << "   - Файл не был закодирован через file_encode_plain\n";
        std::cerr << "   - Файл повреждён или в неправильном формате\n";
        std::cerr << "   - Файл содержит только текст без маркеров\n";
        return false;
    }
    
    size_t first_marker_offset = std::distance(file_buffer.begin(), first_marker_pos);
    std::cout << "🔍 Найден первый маркер на позиции: " << first_marker_offset << " байт\n";
    
    // Не ищем заголовок - полагаемся только на значения из валидных чанков
    // Это более надежно при сильном шуме, так как заголовок может быть поврежден
    uint32_t total_chunks = 0;
    std::map<uint32_t, uint32_t> total_chunks_votes;  // значение -> количество голосов
    
    std::cout << "📊 Буду определять количество чанков из валидных чанков (заголовка нет - вся информация в чанках)\n";
    
    size_t pos = first_marker_offset;  // Начинаем с первого маркера (файл начинается сразу с чанков)
    
    // Словарь для хранения найденных чанков (по номеру чанка)
    std::map<uint32_t, std::string> found_chunks;
    uint32_t chunks_found = 0;
    uint32_t chunks_skipped = 0;
    uint32_t chunks_crc_failed = 0;
    
    // Ищем чанки по маркерам
    size_t consecutive_failures = 0;  // Счётчик последовательных неудач
    const size_t MAX_CONSECUTIVE_FAILURES = 1000;  // Значительно увеличен лимит для продолжения поиска при шуме
    
    while (pos < file_buffer.size()) {
        size_t old_pos = pos;  // Запоминаем позицию до поиска
        
        // Ищем маркер начала
        auto start_pos = std::search(
            file_buffer.begin() + pos,
            file_buffer.end(),
            START_MARKER,
            START_MARKER + MARKER_SIZE
        );
        
        if (start_pos == file_buffer.end()) {
            // Маркер не найден - заканчиваем поиск
            break;
        }
        
        size_t chunk_start_pos = std::distance(file_buffer.begin(), start_pos) + MARKER_SIZE;
        pos = chunk_start_pos;
        
        // Проверяем, достаточно ли данных для полного 47-байтного чанка
        // Структура: START_MARKER(4) + chunk_num(2) + total_chunks(2) + CRC32(4) + данные(31) + END_MARKER(4) = 47
        const size_t FULL_CHUNK_SIZE = MARKER_SIZE + 2 + 2 + 4 + CHUNK_DATA_SIZE + MARKER_SIZE;  // 47 байт
        
        if (pos + FULL_CHUNK_SIZE - MARKER_SIZE > file_buffer.size()) {
            std::cerr << "⚠️  Недостаточно данных для чтения метаданных чанка\n";
            break;
        }
        
        // Читаем номер чанка (2 байта, uint16_t, little-endian)
        uint16_t chunk_num = file_buffer[pos] |
                            (file_buffer[pos + 1] << 8);
        pos += 2;
        
        // Читаем общее количество чанков (2 байта, uint16_t, little-endian) - избыточная информация
        uint16_t chunk_total_chunks = file_buffer[pos] |
                                      (file_buffer[pos + 1] << 8);
        pos += 2;
        
        // Собираем голоса для определения правильного total_chunks (пока не проверили CRC32)
        // Это значение будет использовано позже, если чанк окажется валидным
        
        // Читаем ожидаемый CRC32 (4 байта, little-endian)
        uint32_t expected_crc = file_buffer[pos] |
                               (file_buffer[pos + 1] << 8) |
                               (file_buffer[pos + 2] << 16) |
                               (file_buffer[pos + 3] << 24);
        pos += 4;
        
        // Проверяем, достаточно ли данных для чтения полного чанка (31 байт данных + END_MARKER)
        if (pos + CHUNK_DATA_SIZE + MARKER_SIZE > file_buffer.size()) {
            std::cerr << "⚠️  Недостаточно данных для чтения полного чанка " << chunk_num << "\n";
            break;
        }
        
        // Извлекаем чанк (всегда 31 байт, последний может быть дополнен нулями при кодировании)
        std::vector<uint8_t> chunk_bytes(
            file_buffer.begin() + pos,
            file_buffer.begin() + pos + CHUNK_DATA_SIZE
        );
        pos += CHUNK_DATA_SIZE;
        
        // Проверяем CRC32
        uint32_t actual_crc = crc32(chunk_bytes.data(), chunk_bytes.size());
        if (actual_crc != expected_crc) {
            // Пропускаем повреждённый пакет, сдвигаемся на 1 байт от маркера
            pos = chunk_start_pos - 1;
            consecutive_failures++;
            chunks_crc_failed++;
            if (consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
                std::cerr << "❌ Слишком много последовательных ошибок, прекращаю поиск\n";
                break;
            }
            continue;
        }
        
        // Проверяем маркер конца
        if (pos + MARKER_SIZE > file_buffer.size()) {
            std::cerr << "⚠️  Недостаточно данных для чтения маркера конца чанка " << chunk_num << "\n";
            break;
        }
        
        bool end_marker_ok = std::equal(
            END_MARKER,
            END_MARKER + MARKER_SIZE,
            file_buffer.begin() + pos
        );
        
        if (!end_marker_ok) {
            // Пропускаем повреждённый пакет, сдвигаемся на 1 байт от маркера
            pos = chunk_start_pos - 1;
            consecutive_failures++;
            chunks_skipped++;
            if (consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
                std::cerr << "❌ Слишком много последовательных ошибок, прекращаю поиск\n";
                break;
            }
            continue;
        }
        
        pos += MARKER_SIZE;
        
        // Сбрасываем счётчик ошибок при успешной обработке
        consecutive_failures = 0;
        
        // Проверяем, что позиция действительно продвинулась
        if (pos <= old_pos) {
            std::cerr << "⚠️  Позиция не продвинулась, возможен бесконечный цикл. Прекращаю поиск.\n";
            break;
        }
        
        // Преобразуем в строку
        std::string chunk(chunk_bytes.begin(), chunk_bytes.end());
        
        // Чанк валиден! Добавляем голос для total_chunks (uint16_t -> uint32_t для совместимости)
        uint32_t chunk_total_chunks_u32 = static_cast<uint32_t>(chunk_total_chunks);
        if (chunk_total_chunks_u32 > 0 && chunk_total_chunks_u32 <= 65535) {
            total_chunks_votes[chunk_total_chunks_u32]++;
        }
        
        // Сохраняем чанк (если ещё не сохранен или если это более поздняя версия)
        if (found_chunks.find(chunk_num) == found_chunks.end() || 
            found_chunks[chunk_num] != chunk) {
            found_chunks[chunk_num] = chunk;
            chunks_found++;
            if (chunks_found % 10 == 0 || chunks_found == total_chunks) {
                std::cout << "✅ Найдено чанков: " << chunks_found << "/" << total_chunks << "\n";
            }
        }
    }
    
    // Определяем правильное значение total_chunks на основе голосования из валидных чанков
    if (!total_chunks_votes.empty()) {
        // Находим наиболее частое значение
        uint32_t most_common_total = 0;
        uint32_t max_votes = 0;
        for (const auto& pair : total_chunks_votes) {
            if (pair.second > max_votes) {
                max_votes = pair.second;
                most_common_total = pair.first;
            }
        }
        
        total_chunks = most_common_total;
        std::cout << "✅ Определено количество чанков из валидных чанков: " << total_chunks 
                  << " (подтверждено " << max_votes << " валидными чанками)\n";
    }
    
    // Если total_chunks всё ещё не определён, используем максимальный найденный номер + 1
    if (total_chunks == 0 && !found_chunks.empty()) {
        uint32_t max_chunk_num = 0;
        for (const auto& pair : found_chunks) {
            if (pair.first > max_chunk_num) {
                max_chunk_num = pair.first;
            }
        }
        total_chunks = max_chunk_num + 1;
        std::cout << "⚠️  Использую максимальный номер найденного чанка + 1: " << total_chunks << "\n";
    }
    
    if (total_chunks == 0) {
        std::cerr << "❌ Не удалось определить общее количество чанков\n";
        return false;
    }
    
    // ЭТАП 2: Целенаправленный поиск пропущенных чанков
    uint32_t chunks_found_primary = chunks_found;  // Сохраняем количество найденных в первичном поиске
    if (total_chunks > 0) {
        std::vector<uint16_t> missing_chunks;
        for (uint16_t i = 0; i < total_chunks; i++) {
            if (found_chunks.find(i) == found_chunks.end()) {
                missing_chunks.push_back(i);
            }
        }
        
        if (!missing_chunks.empty()) {
            std::cout << "🔍 Ищу " << missing_chunks.size() << " пропущенных чанков по их номерам...\n";
            
            for (uint16_t missing_num : missing_chunks) {
                ChunkSearchResult result = find_chunk_by_number(file_buffer, missing_num);
                if (result.found) {
                    found_chunks[missing_num] = result.data;
                    chunks_found++;
                    std::cout << "✅ Найден пропущенный чанк " << missing_num << " на позиции " << result.position << "\n";
                }
            }
            
            uint32_t chunks_found_secondary = chunks_found - chunks_found_primary;
            if (chunks_found_secondary > 0) {
                std::cout << "📊 Целенаправленным поиском найдено дополнительно: " << chunks_found_secondary << " чанков\n";
            }
        }
    }
    
    // Сохраняем найденные чанки в файл
    std::ofstream out_file(output_path, std::ios::binary);
    if (!out_file.is_open()) {
        std::cerr << "❌ Не удалось создать выходной файл: " << output_path << "\n";
        return false;
    }
    
    // Записываем чанки в правильном порядке (без переносов строк между ними)
    for (uint32_t i = 0; i < total_chunks; i++) {
        if (found_chunks.find(i) != found_chunks.end()) {
            std::string chunk_data = found_chunks[i];
            
            // Для последнего чанка убираем нули в конце (если они были добавлены при кодировании)
            if (i == total_chunks - 1 && chunk_data.size() == CHUNK_DATA_SIZE) {
                // Убираем все завершающие нули (заголовка нет, определяем автоматически)
                while (!chunk_data.empty() && chunk_data.back() == '\0') {
                    chunk_data.pop_back();
                }
            }
            
            out_file << chunk_data;
        } else {
            std::cerr << "⚠️  Чанк " << i << " не найден\n";
        }
    }
    
    out_file.close();
    
    // Детальная статистика о пропущенных чанках
    std::vector<uint32_t> still_missing;
    for (uint32_t i = 0; i < total_chunks; i++) {
        if (found_chunks.find(i) == found_chunks.end()) {
            still_missing.push_back(i);
        }
    }
    
    std::cout << "\n📊 Статистика восстановления:\n";
    std::cout << "   ✅ Найдено чанков: " << chunks_found << "/" << total_chunks << "\n";
    if (chunks_found_primary > 0) {
        std::cout << "      - Первичным поиском: " << chunks_found_primary << "\n";
        if (chunks_found > chunks_found_primary) {
            std::cout << "      - Целенаправленным поиском: " << (chunks_found - chunks_found_primary) << "\n";
        }
    }
    std::cout << "   ⚠️  Пропущено при первичном поиске: " << chunks_skipped << "\n";
    std::cout << "   ❌ CRC32 ошибок: " << chunks_crc_failed << "\n";
    
    if (!still_missing.empty()) {
        std::cout << "   ⚠️  Не найдено чанков: " << still_missing.size() << "\n";
        if (still_missing.size() <= 20) {
            std::cout << "   📋 Номера пропущенных чанков: ";
            for (size_t i = 0; i < still_missing.size(); i++) {
                std::cout << still_missing[i];
                if (i < still_missing.size() - 1) std::cout << ", ";
            }
            std::cout << "\n";
        } else {
            std::cout << "   📋 Первые 20 пропущенных: ";
            for (size_t i = 0; i < 20; i++) {
                std::cout << still_missing[i];
                if (i < 19) std::cout << ", ";
            }
            std::cout << " ... (всего " << still_missing.size() << ")\n";
        }
    }
    
    // Вычисляем процент восстановления
    if (total_chunks > 0) {
        double recovery_rate = (double)chunks_found / total_chunks * 100.0;
        std::cout << "   📈 Процент восстановления: " << std::fixed << std::setprecision(1) 
                  << recovery_rate << "%\n";
    }
    
    // Принудительно сбрасываем буфер stdout для гарантированного вывода в GUI
    std::cout.flush();
    
    if (chunks_found > 0) {
        std::cout << "✅ Файл восстановлен: " << output_path << "\n";
        std::cout.flush();  // Сбрасываем буфер перед возвратом
        return true;
    } else {
        std::cerr << "❌ Не удалось найти ни одного чанка\n";
        std::cerr.flush();  // Сбрасываем буфер stderr
        return false;
    }
}

// Гибридное кодирование: шифрование через DigitalCodec + plain фрагментация
bool encode_file_to_container_hybrid(const std::string& input_path,
                                     const std::string& output_path,
                                     const std::string& intermediate_path,
                                     digitalcodec::DigitalCodec& codec) {
    std::cout << "🔐 Начинаем гибридное кодирование: " << input_path << "\n";
    std::cout << "   Этап 1: Шифрование через DigitalCodec\n";
    std::cout << "   Этап 2: Plain фрагментация зашифрованных данных\n";
    
    // Размер чанка данных (для plain фрагментации)
    const size_t CHUNK_DATA_SIZE = 31;  // 31 байт данных на чанк
    
    // 1. Читаем исходный файл
    std::ifstream in_file(input_path, std::ios::binary);
    if (!in_file.is_open()) {
        std::cerr << "❌ Не удалось открыть файл: " << input_path << "\n";
        return false;
    }
    
    std::vector<uint8_t> file_data((std::istreambuf_iterator<char>(in_file)),
                                   std::istreambuf_iterator<char>());
    in_file.close();
    
    if (file_data.empty()) {
        std::cerr << "❌ Файл пуст\n";
        return false;
    }
    
    size_t original_file_size = file_data.size();
    std::cout << "📊 Размер исходного файла: " << original_file_size << " байт\n";
    
    // 2. Шифруем через DigitalCodec
    codec.reset();
    std::vector<uint8_t> encrypted_data = codec.encodeMessage(file_data);
    
    std::cout << "✅ Файл зашифрован через DigitalCodec\n";
    std::cout << "📊 Размер зашифрованных данных: " << encrypted_data.size() << " байт\n";
    
    // 3. Сохраняем промежуточный файл (если указан путь)
    if (!intermediate_path.empty()) {
        std::ofstream intermediate_file(intermediate_path, std::ios::binary);
        if (intermediate_file.is_open()) {
            intermediate_file.write(reinterpret_cast<const char*>(encrypted_data.data()), encrypted_data.size());
            intermediate_file.close();
            std::cout << "💾 Промежуточный зашифрованный файл сохранен: " << intermediate_path << "\n";
        } else {
            std::cerr << "⚠️  Не удалось сохранить промежуточный файл: " << intermediate_path << "\n";
        }
    }
    
    // 4. Применяем plain фрагментацию к зашифрованным данным
    std::vector<std::vector<uint8_t>> chunks;
    
    // Первый чанк: исходная длина файла (4 байта) + данные (27 байт) = 31 байт
    if (encrypted_data.size() > 0) {
        std::vector<uint8_t> first_chunk;
        first_chunk.reserve(CHUNK_DATA_SIZE);
        
        // Добавляем исходную длину файла (4 байта, little-endian)
        uint32_t original_len = static_cast<uint32_t>(original_file_size);
        first_chunk.push_back(static_cast<uint8_t>(original_len & 0xFF));
        first_chunk.push_back(static_cast<uint8_t>((original_len >> 8) & 0xFF));
        first_chunk.push_back(static_cast<uint8_t>((original_len >> 16) & 0xFF));
        first_chunk.push_back(static_cast<uint8_t>((original_len >> 24) & 0xFF));
        
        // Добавляем данные из зашифрованного файла (27 байт)
        size_t first_chunk_data_size = std::min(static_cast<size_t>(27), encrypted_data.size());
        first_chunk.insert(first_chunk.end(), 
                          encrypted_data.begin(), 
                          encrypted_data.begin() + first_chunk_data_size);
        
        // Дополняем до 31 байта нулями (если нужно)
        if (first_chunk.size() < CHUNK_DATA_SIZE) {
            first_chunk.resize(CHUNK_DATA_SIZE, 0);
        }
        
        chunks.push_back(first_chunk);
    }
    
    // Остальные чанки: по 31 байт данных каждый (начиная с позиции 27)
    size_t pos = 27;
    while (pos < encrypted_data.size()) {
        size_t chunk_len = std::min(CHUNK_DATA_SIZE, encrypted_data.size() - pos);
        std::vector<uint8_t> chunk(encrypted_data.begin() + pos, 
                                  encrypted_data.begin() + pos + chunk_len);
        
        // Дополняем до 31 байта нулями (если нужно)
        if (chunk.size() < CHUNK_DATA_SIZE) {
            chunk.resize(CHUNK_DATA_SIZE, 0);
        }
        
        chunks.push_back(chunk);
        pos += chunk_len;
    }
    
    if (chunks.empty()) {
        std::cerr << "❌ Не удалось создать чанки\n";
        return false;
    }
    
    std::cout << "📊 Создано чанков: " << chunks.size() << " (по " << CHUNK_DATA_SIZE << " байт данных)\n";
    
    // 5. Записываем чанки с маркерами
    std::ofstream out_file(output_path, std::ios::binary);
    if (!out_file.is_open()) {
        std::cerr << "❌ Не удалось создать выходной файл: " << output_path << "\n";
        return false;
    }
    
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;
    
    uint16_t total_chunks = static_cast<uint16_t>(chunks.size());
    
    for (uint32_t i = 0; i < chunks.size(); i++) {
        const std::vector<uint8_t>& chunk = chunks[i];
        
        // Вычисляем CRC32 чанка
        uint32_t chunk_crc = crc32(chunk.data(), chunk.size());
        
        // Записываем маркер начала
        out_file.write(reinterpret_cast<const char*>(START_MARKER), MARKER_SIZE);
        
        // Записываем номер чанка (2 байта, uint16_t, little-endian)
        uint16_t chunk_num = static_cast<uint16_t>(i);
        uint8_t chunk_num_bytes[2] = {
            static_cast<uint8_t>(chunk_num & 0xFF),
            static_cast<uint8_t>((chunk_num >> 8) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(chunk_num_bytes), 2);
        
        // Записываем общее количество чанков (2 байта, uint16_t, little-endian)
        uint8_t total_chunks_bytes[2] = {
            static_cast<uint8_t>(total_chunks & 0xFF),
            static_cast<uint8_t>((total_chunks >> 8) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(total_chunks_bytes), 2);
        
        // Записываем CRC32 (4 байта, little-endian)
        uint8_t crc_bytes[4] = {
            static_cast<uint8_t>(chunk_crc & 0xFF),
            static_cast<uint8_t>((chunk_crc >> 8) & 0xFF),
            static_cast<uint8_t>((chunk_crc >> 16) & 0xFF),
            static_cast<uint8_t>((chunk_crc >> 24) & 0xFF)
        };
        out_file.write(reinterpret_cast<const char*>(crc_bytes), 4);
        
        // Записываем данные чанка (31 байт)
        out_file.write(reinterpret_cast<const char*>(chunk.data()), CHUNK_DATA_SIZE);
        
        // Записываем маркер конца
        out_file.write(reinterpret_cast<const char*>(END_MARKER), MARKER_SIZE);
    }
    
    out_file.close();
    
    std::cout << "✅ Гибридное кодирование завершено успешно!\n";
    std::cout << "📊 Выходной файл: " << output_path << " (" << chunks.size() << " чанков)\n";
    
    return true;
}

// Гибридное декодирование: plain поиск фрагментов + расшифровка через DigitalCodec
bool decode_container_to_file_hybrid(const std::string& container_path,
                                     const std::string& output_path,
                                     const std::string& intermediate_path,
                                     digitalcodec::DigitalCodec& codec) {
    std::cout << "📥 Начинаем гибридное декодирование контейнера: " << container_path << "\n";
    std::cout << "   Этап 1: Поиск фрагментов в шуме (plain метод)\n";
    std::cout << "   Этап 2: Сбор зашифрованных данных\n";
    std::cout << "   Этап 3: Расшифровка через DigitalCodec\n";
    
    // Константы маркеров
    const uint8_t START_MARKER[] = {0xAA, 0x55, 0xAA, 0x55};
    const uint8_t END_MARKER[] = {0x55, 0xAA, 0x55, 0xAA};
    const size_t MARKER_SIZE = 4;
    const size_t CHUNK_DATA_SIZE = 31;  // Все фрагменты одинаковые: 31 байт данных
    
    // Открываем контейнер
    std::ifstream in_file(container_path, std::ios::binary);
    if (!in_file.is_open()) {
        std::cerr << "❌ Не удалось открыть контейнер: " << container_path << "\n";
        return false;
    }
    
    // Читаем весь файл в буфер
    in_file.seekg(0, std::ios::end);
    size_t file_size = in_file.tellg();
    in_file.seekg(0, std::ios::beg);
    
    std::vector<uint8_t> file_buffer(file_size);
    in_file.read(reinterpret_cast<char*>(file_buffer.data()), file_size);
    in_file.close();
    
    std::cout << "📊 Размер файла: " << file_size << " байт\n";
    
    // Ищем первый маркер
    auto first_marker_pos = std::search(
        file_buffer.begin(),
        file_buffer.end(),
        START_MARKER,
        START_MARKER + MARKER_SIZE
    );
    
    if (first_marker_pos == file_buffer.end()) {
        std::cerr << "❌ Маркеры начала не найдены в файле!\n";
        return false;
    }
    
    size_t first_marker_offset = std::distance(file_buffer.begin(), first_marker_pos);
    std::cout << "🔍 Найден первый маркер на позиции: " << first_marker_offset << " байт\n";
    
    // Словарь для хранения найденных чанков
    std::map<uint32_t, std::vector<uint8_t>> found_chunks;
    uint32_t chunks_found = 0;
    uint32_t chunks_skipped = 0;
    uint32_t chunks_crc_failed = 0;
    uint32_t total_chunks = 0;
    std::map<uint32_t, uint32_t> total_chunks_votes;
    
    size_t pos = first_marker_offset;
    size_t consecutive_failures = 0;
    const size_t MAX_CONSECUTIVE_FAILURES = 1000;
    
    // Ищем чанки по маркерам (та же логика, что и в decode_container_to_file_plain)
    while (pos < file_buffer.size()) {
        size_t old_pos = pos;
        
        // Ищем маркер начала
        auto start_pos = std::search(
            file_buffer.begin() + pos,
            file_buffer.end(),
            START_MARKER,
            START_MARKER + MARKER_SIZE
        );
        
        if (start_pos == file_buffer.end()) {
            break;
        }
        
        size_t chunk_start_pos = std::distance(file_buffer.begin(), start_pos) + MARKER_SIZE;
        pos = chunk_start_pos;
        
        // Проверяем достаточность данных
        const size_t FULL_CHUNK_SIZE = MARKER_SIZE + 2 + 2 + 4 + CHUNK_DATA_SIZE + MARKER_SIZE;
        if (pos + FULL_CHUNK_SIZE - MARKER_SIZE > file_buffer.size()) {
            break;
        }
        
        // Читаем номер чанка (2 байта, uint16_t, little-endian)
        uint16_t chunk_num = file_buffer[pos] | (file_buffer[pos + 1] << 8);
        pos += 2;
        
        // Читаем общее количество чанков (2 байта, uint16_t, little-endian)
        uint16_t chunk_total_chunks = file_buffer[pos] | (file_buffer[pos + 1] << 8);
        pos += 2;
        
        // Читаем ожидаемый CRC32 (4 байта, little-endian)
        uint32_t expected_crc = file_buffer[pos] |
                               (file_buffer[pos + 1] << 8) |
                               (file_buffer[pos + 2] << 16) |
                               (file_buffer[pos + 3] << 24);
        pos += 4;
        
        // Проверяем достаточность данных для чтения полного чанка
        if (pos + CHUNK_DATA_SIZE + MARKER_SIZE > file_buffer.size()) {
            break;
        }
        
        // Извлекаем данные чанка (31 байт)
        std::vector<uint8_t> chunk_bytes(
            file_buffer.begin() + pos,
            file_buffer.begin() + pos + CHUNK_DATA_SIZE
        );
        pos += CHUNK_DATA_SIZE;
        
        // Проверяем CRC32
        uint32_t actual_crc = crc32(chunk_bytes.data(), chunk_bytes.size());
        if (actual_crc != expected_crc) {
            pos = chunk_start_pos - 1;
            consecutive_failures++;
            chunks_crc_failed++;
            if (consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
                std::cerr << "❌ Слишком много последовательных ошибок, прекращаю поиск\n";
                break;
            }
            continue;
        }
        
        // Проверяем маркер конца
        if (pos + MARKER_SIZE > file_buffer.size()) {
            break;
        }
        
        bool end_marker_ok = std::equal(
            END_MARKER,
            END_MARKER + MARKER_SIZE,
            file_buffer.begin() + pos
        );
        
        if (!end_marker_ok) {
            pos = chunk_start_pos - 1;
            consecutive_failures++;
            chunks_skipped++;
            if (consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
                std::cerr << "❌ Слишком много последовательных ошибок, прекращаю поиск\n";
                break;
            }
            continue;
        }
        
        pos += MARKER_SIZE;
        consecutive_failures = 0;
        
        if (pos <= old_pos) {
            std::cerr << "⚠️  Позиция не продвинулась, возможен бесконечный цикл. Прекращаю поиск.\n";
            break;
        }
        
        // Сохраняем чанк
        found_chunks[chunk_num] = chunk_bytes;
        chunks_found++;
        total_chunks_votes[chunk_total_chunks]++;
    }
    
    // Определяем правильное значение total_chunks
    if (!total_chunks_votes.empty()) {
        uint32_t most_common_total = 0;
        uint32_t max_votes = 0;
        for (const auto& pair : total_chunks_votes) {
            if (pair.second > max_votes) {
                max_votes = pair.second;
                most_common_total = pair.first;
            }
        }
        total_chunks = most_common_total;
        std::cout << "✅ Определено количество чанков: " << total_chunks 
                  << " (подтверждено " << max_votes << " валидными чанками)\n";
    }
    
    if (total_chunks == 0) {
        std::cerr << "❌ Не удалось определить общее количество чанков\n";
        return false;
    }
    
    if (chunks_found == 0) {
        std::cerr << "❌ Не удалось найти ни одного чанка\n";
        return false;
    }
    
    std::cout << "📊 Найдено чанков: " << chunks_found << "/" << total_chunks << "\n";
    std::cout << "📊 Пропущено: " << chunks_skipped << ", CRC32 ошибок: " << chunks_crc_failed << "\n";
    
    // Собираем зашифрованные данные из чанков
    std::vector<uint8_t> encrypted_data;
    uint32_t original_file_size = 0;
    bool first_chunk_processed = false;
    
    for (uint32_t i = 0; i < total_chunks; i++) {
        if (found_chunks.find(i) == found_chunks.end()) {
            std::cerr << "⚠️  Чанк " << i << " не найден\n";
            // Заполняем пропущенные чанки нулями
            if (i == 0 && !first_chunk_processed) {
                encrypted_data.insert(encrypted_data.end(), 27, 0);
            } else {
                encrypted_data.insert(encrypted_data.end(), CHUNK_DATA_SIZE, 0);
            }
            continue;
        }
        
        const std::vector<uint8_t>& chunk = found_chunks[i];
        
        if (i == 0 && !first_chunk_processed) {
            // Первый чанк содержит исходную длину файла (4 байта) + данные (27 байт) = 31 байт
            if (chunk.size() >= 4) {
                original_file_size = chunk[0] |
                                   (chunk[1] << 8) |
                                   (chunk[2] << 16) |
                                   (chunk[3] << 24);
                
                std::cout << "📊 Исходный размер файла: " << original_file_size << " байт\n";
                
                // Добавляем данные из первого чанка (пропускаем первые 4 байта - длина)
                if (chunk.size() > 4) {
                    size_t data_size = std::min(static_cast<size_t>(27), chunk.size() - 4);
                    encrypted_data.insert(encrypted_data.end(),
                                         chunk.begin() + 4,
                                         chunk.begin() + 4 + data_size);
                } else {
                    encrypted_data.insert(encrypted_data.end(), 27, 0);
                }
            } else {
                encrypted_data.insert(encrypted_data.end(), 4, 0);
                encrypted_data.insert(encrypted_data.end(), 27, 0);
            }
            first_chunk_processed = true;
        } else {
            // Остальные чанки содержат только данные (31 байт каждый)
            if (chunk.size() >= CHUNK_DATA_SIZE) {
                encrypted_data.insert(encrypted_data.end(), chunk.begin(), chunk.begin() + CHUNK_DATA_SIZE);
            } else {
                encrypted_data.insert(encrypted_data.end(), chunk.begin(), chunk.end());
                encrypted_data.insert(encrypted_data.end(), CHUNK_DATA_SIZE - chunk.size(), 0);
            }
        }
    }
    
    std::cout << "✅ Собрано зашифрованных данных: " << encrypted_data.size() << " байт\n";
    
    // Убираем padding из последнего чанка (если нужно)
    // Вычисляем ожидаемый размер зашифрованных данных
    // encodeMessage добавляет 2 байта длины в начале, поэтому нужно учесть это
    // Но мы не знаем точный размер, поэтому просто убираем завершающие нули
    while (!encrypted_data.empty() && encrypted_data.back() == 0) {
        encrypted_data.pop_back();
    }
    
    // Сохраняем промежуточный файл (если указан путь)
    if (!intermediate_path.empty()) {
        std::ofstream intermediate_file(intermediate_path, std::ios::binary);
        if (intermediate_file.is_open()) {
            intermediate_file.write(reinterpret_cast<const char*>(encrypted_data.data()), encrypted_data.size());
            intermediate_file.close();
            std::cout << "💾 Промежуточный зашифрованный файл сохранен: " << intermediate_path << "\n";
        } else {
            std::cerr << "⚠️  Не удалось сохранить промежуточный файл: " << intermediate_path << "\n";
        }
    }
    
    // Расшифровываем через DigitalCodec
    codec.reset();
    std::vector<uint8_t> decrypted_data;
    
    try {
        // Используем original_file_size как expected_len, если он известен, иначе 0 (автоопределение)
        size_t expected_len = (original_file_size > 0) ? original_file_size : 0;
        decrypted_data = codec.decodeMessage(encrypted_data, expected_len);
    } catch (const std::exception& e) {
        std::cerr << "❌ Ошибка расшифровки через DigitalCodec: " << e.what() << "\n";
        return false;
    }
    
    // Обрезаем до исходной длины (если нужно)
    if (original_file_size > 0 && decrypted_data.size() > original_file_size) {
        decrypted_data.resize(original_file_size);
    }
    
    std::cout << "✅ Расшифровано данных: " << decrypted_data.size() << " байт\n";
    
    // Сохраняем исходный файл
    std::ofstream out_file(output_path, std::ios::binary);
    if (!out_file.is_open()) {
        std::cerr << "❌ Не удалось создать выходной файл: " << output_path << "\n";
        return false;
    }
    
    out_file.write(reinterpret_cast<const char*>(decrypted_data.data()), decrypted_data.size());
    out_file.close();
    
    // Вычисляем статистику восстановления
    double chunks_recovery_rate = 0.0;
    if (total_chunks > 0) {
        chunks_recovery_rate = (double)chunks_found / total_chunks * 100.0;
    }
    
    double data_recovery_rate = 0.0;
    if (original_file_size > 0) {
        data_recovery_rate = (double)decrypted_data.size() / original_file_size * 100.0;
    }
    
    std::cout << "\n📊 Итоговая статистика восстановления:\n";
    std::cout << "   📦 Чанков восстановлено: " << chunks_found << "/" << total_chunks;
    if (total_chunks > 0) {
        std::cout << " (" << std::fixed << std::setprecision(1) << chunks_recovery_rate << "%)";
    }
    std::cout << "\n";
    std::cout << "   📄 Данных восстановлено: " << decrypted_data.size() << "/" << original_file_size << " байт";
    if (original_file_size > 0) {
        std::cout << " (" << std::fixed << std::setprecision(1) << data_recovery_rate << "%)";
    }
    std::cout << "\n";
    
    std::cout << "✅ Гибридное декодирование завершено успешно!\n";
    std::cout << "📊 Восстановленный файл: " << output_path << " (" << decrypted_data.size() << " байт)\n";
    
    return true;
}

} // namespace filetransfer
