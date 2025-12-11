#include <iostream>
#include <string>
#include <vector>
#include "digital_codec.h"
#include "file_transfer.h"
#include <sodium.h>

int main(int argc, char *argv[]) {
    if (argc < 5) {
        std::cerr << "Использование: " << argv[0] 
                  << " <input_file> <output_container> --codec <csv_path> [--M <M>] [--Q <Q>] [--fun <funType>] [--h1 <h1>] [--h2 <h2>]\n";
        std::cerr << "\nПараметры:\n";
        std::cerr << "  <input_file>        - путь к исходному файлу\n";
        std::cerr << "  <output_container>  - путь к выходному контейнеру\n";
        std::cerr << "  --codec <csv_path>  - путь к CSV файлу с коэффициентами (обязательно)\n";
        std::cerr << "  --M <M>             - разрядность вычислителя (1-31, по умолчанию: 8)\n";
        std::cerr << "  --Q <Q>             - количество информационных бит (1-16, по умолчанию: 2)\n";
        std::cerr << "  --fun <funType>     - тип функции (1-5, по умолчанию: 1)\n";
        std::cerr << "  --h1 <h1>           - начальное состояние h1 (по умолчанию: 7)\n";
        std::cerr << "  --h2 <h2>           - начальное состояние h2 (по умолчанию: 23)\n";
        return 1;
    }
    
    if (sodium_init() < 0) {
        std::cerr << "❌ Не удалось инициализировать libsodium\n";
        return 1;
    }
    
    std::string input_path;
    std::string output_path;
    std::string codec_csv;
    digitalcodec::CodecParams codec_params; // defaults: M=8, Q=2, fun=1, h1=7, h2=23
    
    // Парсинг аргументов
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        
        if (arg == "--codec" && i + 1 < argc) {
            codec_csv = argv[++i];
        } else if (arg == "--M" && i + 1 < argc) {
            codec_params.bitsM = std::stoi(argv[++i]);
        } else if (arg == "--Q" && i + 1 < argc) {
            codec_params.bitsQ = std::stoi(argv[++i]);
        } else if (arg == "--fun" && i + 1 < argc) {
            codec_params.funType = std::stoi(argv[++i]);
        } else if (arg == "--h1" && i + 1 < argc) {
            codec_params.h1 = std::stoi(argv[++i]);
        } else if (arg == "--h2" && i + 1 < argc) {
            codec_params.h2 = std::stoi(argv[++i]);
        } else if (input_path.empty()) {
            input_path = arg;
        } else if (output_path.empty()) {
            output_path = arg;
        }
    }
    
    // Валидация обязательных параметров
    if (input_path.empty()) {
        std::cerr << "❌ Не указан входной файл!\n";
        return 1;
    }
    
    if (output_path.empty()) {
        std::cerr << "❌ Не указан выходной контейнер!\n";
        return 1;
    }
    
    if (codec_csv.empty()) {
        std::cerr << "❌ Не указан путь к CSV файлу с коэффициентами (--codec)!\n";
        return 1;
    }
    
    // Инициализация кодека
    digitalcodec::DigitalCodec codec;
    try {
        codec.configure(codec_params);
        codec.loadCoefficientsCSV(codec_csv);
        codec.reset();
        
        std::cout << "🎛️  Цифровой кодек инициализирован (M=" << codec_params.bitsM
                  << ", Q=" << codec_params.bitsQ << ", fun=" << codec_params.funType << ")\n";
    } catch (const std::exception &e) {
        std::cerr << "❌ Ошибка инициализации кодека: " << e.what() << "\n";
        return 1;
    }
    
    // Кодирование файла
    if (!filetransfer::encode_file_to_container(input_path, output_path, codec)) {
        std::cerr << "❌ Ошибка при кодировании файла\n";
        return 1;
    }
    
    std::cout << "✅ Кодирование завершено успешно!\n";
    return 0;
}

