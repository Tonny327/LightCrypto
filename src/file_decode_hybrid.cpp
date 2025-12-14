#include <iostream>
#include <string>
#include "file_transfer.h"
#include "digital_codec.h"

int main(int argc, char *argv[]) {
    if (argc < 3) {
        std::cerr << "Использование: " << argv[0] 
                  << " <input_container> <output_file> [--codec <csv_path>] [--M <M>] [--Q <Q>] [--fun <funType>] [--h1 <h1>] [--h2 <h2>] [--intermediate <path>]\n";
        std::cerr << "\nПараметры:\n";
        std::cerr << "  <input_container>   - путь к контейнеру\n";
        std::cerr << "  <output_file>       - путь к выходному файлу\n";
        std::cerr << "  --codec <csv_path>  - путь к CSV файлу с коэффициентами (обязательно)\n";
        std::cerr << "  --M <M>             - разрядность вычислителя (по умолчанию: 8)\n";
        std::cerr << "  --Q <Q>             - количество информационных бит на символ (по умолчанию: 6)\n";
        std::cerr << "  --fun <funType>     - тип функции (1-5, по умолчанию: 1)\n";
        std::cerr << "  --h1 <h1>           - начальное состояние 1 (по умолчанию: 7)\n";
        std::cerr << "  --h2 <h2>           - начальное состояние 2 (по умолчанию: 23)\n";
        std::cerr << "  --intermediate <path> - путь для сохранения промежуточного зашифрованного файла (опционально)\n";
        std::cerr << "\nПример:\n";
        std::cerr << "  " << argv[0] << " received.bin output.txt --codec coefficients.csv --M 8 --Q 6\n";
        return 1;
    }
    
    std::string input_path = argv[1];
    std::string output_path = argv[2];
    std::string codec_csv;
    std::string intermediate_path;
    digitalcodec::CodecParams codec_params; // defaults: M=8, Q=6, fun=1, h1=7, h2=23
    
    // Парсинг аргументов
    for (int i = 3; i < argc; ++i) {
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
        } else if (arg == "--intermediate" && i + 1 < argc) {
            intermediate_path = argv[++i];
        }
    }
    
    if (codec_csv.empty()) {
        std::cerr << "❌ Ошибка: необходимо указать путь к CSV файлу с коэффициентами (--codec)\n";
        return 1;
    }
    
    // Создаем и настраиваем кодек
    digitalcodec::DigitalCodec codec;
    try {
        codec.configure(codec_params);
        codec.loadCoefficientsCSV(codec_csv);
        codec.reset();
    } catch (const std::exception& e) {
        std::cerr << "❌ Ошибка настройки кодека: " << e.what() << "\n";
        return 1;
    }
    
    // Гибридное декодирование: plain поиск фрагментов + расшифровка через DigitalCodec
    if (!filetransfer::decode_container_to_file_hybrid(input_path, output_path, intermediate_path, codec)) {
        std::cerr << "❌ Ошибка при гибридном декодировании контейнера\n";
        return 1;
    }
    
    std::cout << "✅ Гибридное декодирование завершено успешно!\n";
    return 0;
}
