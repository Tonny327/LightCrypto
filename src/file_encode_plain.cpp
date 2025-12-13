#include <iostream>
#include <string>
#include "file_transfer.h"

int main(int argc, char *argv[]) {
    if (argc < 3) {
        std::cerr << "Использование: " << argv[0] 
                  << " <input_file> <output_container>\n";
        std::cerr << "\nПараметры:\n";
        std::cerr << "  <input_file>        - путь к исходному текстовому файлу\n";
        std::cerr << "  <output_container>  - путь к выходному контейнеру\n";
        std::cerr << "\nПример:\n";
        std::cerr << "  " << argv[0] << " input.txt output.bin\n";
        return 1;
    }
    
    std::string input_path = argv[1];
    std::string output_path = argv[2];
    
    // Кодирование файла без шифрования
    if (!filetransfer::encode_file_to_container_plain(input_path, output_path)) {
        std::cerr << "❌ Ошибка при кодировании файла\n";
        return 1;
    }
    
    std::cout << "✅ Кодирование завершено успешно!\n";
    return 0;
}




