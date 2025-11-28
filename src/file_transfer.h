#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <cstring>

// Протокол передачи файлов для LightCrypto
// Поддержка фрагментации больших файлов на чанки

namespace filetransfer {

// Магическое число для идентификации пакетов протокола
constexpr uint32_t MAGIC_FILE_HEADER = 0x46494C45;  // "FILE"
constexpr uint32_t MAGIC_FILE_CHUNK = 0x43484E4B;   // "CHNK"
constexpr uint32_t MAGIC_FILE_ACK = 0x41434B00;     // "ACK\0"
constexpr uint32_t MAGIC_SYNC_REQUEST = 0x53594E43; // "SYNC" - запрос синхронизации

// Размер чанка данных (без заголовков)
// Увеличено для лучшей пропускной способности (было 1400)
constexpr size_t CHUNK_DATA_SIZE = 8192;  // Больший размер = меньше overhead от заголовков

// Максимальное количество попыток передачи
constexpr int MAX_RETRIES = 3;

// Таймаут ожидания подтверждения (миллисекунды)
// Уменьшен для более быстрой реакции (было 5000)
constexpr int ACK_TIMEOUT_MS = 1000;

// Структура заголовка файла
struct FileHeader {
    uint32_t magic;           // Магическое число MAGIC_FILE_HEADER
    uint32_t file_size;       // Размер исходного файла в байтах
    uint32_t total_chunks;    // Общее количество чанков
    uint32_t chunk_size;      // Размер одного чанка (обычно CHUNK_DATA_SIZE)
    uint8_t file_hash[32];    // SHA-256 хеш исходного файла
    uint32_t filename_len;    // Длина имени файла
    // После этой структуры следует имя файла (filename_len байт)
    
    FileHeader() : magic(MAGIC_FILE_HEADER), file_size(0), total_chunks(0), 
                   chunk_size(CHUNK_DATA_SIZE), filename_len(0) {
        std::memset(file_hash, 0, sizeof(file_hash));
    }
};

// Структура заголовка чанка
struct ChunkHeader {
    uint32_t magic;           // Магическое число MAGIC_FILE_CHUNK
    uint32_t chunk_index;     // Порядковый номер чанка (0-based)
    uint32_t total_chunks;    // Общее количество чанков
    uint32_t data_size;       // Размер данных в этом чанке
    uint32_t crc32;           // Контрольная сумма CRC32 данных чанка
    // После этой структуры следуют данные чанка (data_size байт)
    
    ChunkHeader() : magic(MAGIC_FILE_CHUNK), chunk_index(0), 
                    total_chunks(0), data_size(0), crc32(0) {}
};

// Структура подтверждения
struct ChunkAck {
    uint32_t magic;           // Магическое число MAGIC_FILE_ACK
    uint32_t chunk_index;     // Номер подтвержденного чанка
    uint32_t status;          // 0 = OK, 1 = REQUEST_RESEND, 2 = ERROR
    
    ChunkAck() : magic(MAGIC_FILE_ACK), chunk_index(0), status(0) {}
};

// Структура запроса синхронизации состояний кодека
struct SyncRequest {
    uint32_t magic;           // Магическое число MAGIC_SYNC_REQUEST
    uint32_t expected_chunk;  // Ожидаемый номер чанка (для диагностики)
    
    SyncRequest() : magic(MAGIC_SYNC_REQUEST), expected_chunk(0) {}
};

// Вычисление CRC32
uint32_t crc32(const uint8_t* data, size_t length);

// Вычисление SHA-256 хеша файла
void compute_file_hash(const std::vector<uint8_t>& file_data, uint8_t hash[32]);

// Сериализация заголовка файла в байты
std::vector<uint8_t> serialize_file_header(const FileHeader& header, const std::string& filename);

// Десериализация заголовка файла из байтов
bool deserialize_file_header(const uint8_t* data, size_t size, FileHeader& header, std::string& filename);

// Сериализация чанка в байты
std::vector<uint8_t> serialize_chunk(const ChunkHeader& header, const uint8_t* data);

// Десериализация чанка из байтов
bool deserialize_chunk(const uint8_t* data, size_t size, ChunkHeader& header, std::vector<uint8_t>& chunk_data);

// Сериализация подтверждения в байты
std::vector<uint8_t> serialize_ack(const ChunkAck& ack);

// Десериализация подтверждения из байтов
bool deserialize_ack(const uint8_t* data, size_t size, ChunkAck& ack);

// Сериализация запроса синхронизации в байты
std::vector<uint8_t> serialize_sync_request(const SyncRequest& request);

// Десериализация запроса синхронизации из байтов
bool deserialize_sync_request(const uint8_t* data, size_t size, SyncRequest& request);

// Класс для управления отправкой файла
class FileSender {
public:
    FileSender() = default;
    
    // Загрузить файл для отправки
    bool load_file(const std::string& filepath);
    
    // Получить заголовок файла
    FileHeader get_header() const { return header_; }
    
    // Получить имя файла
    std::string get_filename() const { return filename_; }
    
    // Получить общее количество чанков
    uint32_t get_total_chunks() const { return header_.total_chunks; }
    
    // Получить чанк по индексу
    bool get_chunk(uint32_t index, ChunkHeader& chunk_header, std::vector<uint8_t>& chunk_data);
    
    // Получить данные файла
    const std::vector<uint8_t>& get_file_data() const { return file_data_; }
    
private:
    std::string filename_;
    std::vector<uint8_t> file_data_;
    FileHeader header_;
};

// Класс для управления приемом файла
class FileReceiver {
public:
    FileReceiver() = default;
    
    // Инициализировать прием на основе заголовка
    bool initialize(const FileHeader& header, const std::string& filename);
    
    // Добавить полученный чанк
    bool add_chunk(const ChunkHeader& chunk_header, const std::vector<uint8_t>& chunk_data);
    
    // Проверить, все ли чанки получены
    bool is_complete() const;
    
    // Получить процент завершения
    float get_progress() const;
    
    // Получить количество полученных чанков
    uint32_t get_received_count() const { return received_count_; }
    
    // Получить общее количество чанков
    uint32_t get_total_chunks() const { return header_.total_chunks; }
    
    // Получить размер файла в байтах
    uint32_t get_file_size() const { return header_.file_size; }
    
    // Сохранить файл на диск
    bool save_file(const std::string& output_path);
    
    // Проверить целостность полученного файла
    bool verify_integrity() const;
    
    // Получить список недостающих чанков
    std::vector<uint32_t> get_missing_chunks() const;
    
private:
    FileHeader header_;
    std::string filename_;
    std::vector<bool> received_chunks_;
    std::vector<std::vector<uint8_t>> chunk_buffers_;
    uint32_t received_count_;
};

} // namespace filetransfer

