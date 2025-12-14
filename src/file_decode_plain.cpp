#include <iostream>
#include <string>
#include "file_transfer.h"

int main(int argc, char *argv[]) {
    if (argc < 3) {
        std::cerr << "Использование: " << argv[0] 
                  << " <input_container> <output_file>\n";
        std::cerr << "\nПараметры:\n";
        std::cerr << "  <input_container>   - путь к контейнеру\n";
        std::cerr << "  <output_file>       - путь к выходному файлу\n";
        std::cerr << "\nПример:\n";
        std::cerr << "  " << argv[0] << " received.bin output.txt\n";
        return 1;
    }
    
    std::string input_path = argv[1];
    std::string output_path = argv[2];
    
    // Декодирование контейнера без шифрования
    if (!filetransfer::decode_container_to_file_plain(input_path, output_path)) {
        std::cerr << "❌ Ошибка при декодировании контейнера\n";
        return 1;
    }
    
    std::cout << "✅ Декодирование завершено успешно!\n";
    return 0;
}





