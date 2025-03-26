#include <sodium.h>
#include <iostream>
#include <chrono>
#include <vector>

int main() {
    if (sodium_init() < 0) {
        std::cerr << "❌ Не удалось инициализировать libsodium\n";
        return 1;
    }

    const size_t MESSAGE_SIZE = 10 * 1024 * 1024; // 10 МБ
    std::vector<unsigned char> message(MESSAGE_SIZE);
    randombytes_buf(message.data(), MESSAGE_SIZE);

    std::vector<unsigned char> key(crypto_aead_chacha20poly1305_IETF_KEYBYTES);
    std::vector<unsigned char> nonce(crypto_aead_chacha20poly1305_IETF_NPUBBYTES);
    randombytes_buf(key.data(), key.size());
    randombytes_buf(nonce.data(), nonce.size());

    std::vector<unsigned char> ciphertext(MESSAGE_SIZE + crypto_aead_chacha20poly1305_IETF_ABYTES);
    std::vector<unsigned char> decrypted(MESSAGE_SIZE);

    unsigned long long ciphertext_len;
    unsigned long long decrypted_len;

    auto start = std::chrono::high_resolution_clock::now();

    // Шифрование
    crypto_aead_chacha20poly1305_ietf_encrypt(
        ciphertext.data(), &ciphertext_len,
        message.data(), message.size(),
        nullptr, 0, nullptr, nonce.data(), key.data()
    );

    // Расшифровка с проверкой результата
    int result = crypto_aead_chacha20poly1305_ietf_decrypt(
        decrypted.data(), &decrypted_len,
        nullptr,
        ciphertext.data(), ciphertext_len,
        nullptr, 0, nonce.data(), key.data()
    );

    auto end = std::chrono::high_resolution_clock::now();

    if (result != 0) {
        std::cerr << "❌ Расшифровка не удалась (возможно, неверный ключ или повреждённые данные)\n";
        return 1;
    }

    // Проверка совпадения данных
    if (decrypted_len != message.size() || !std::equal(message.begin(), message.end(), decrypted.begin())) {
        std::cerr << "❌ Расшифрованные данные не совпадают с исходными\n";
        return 1;
    }

    double duration_sec = std::chrono::duration<double>(end - start).count();
    double speed_mb_per_sec = MESSAGE_SIZE / (1024.0 * 1024.0) / duration_sec;

    std::cout << "✅ Шифрование + расшифровка успешны\n";
    std::cout << "📦 Объём: " << MESSAGE_SIZE / (1024 * 1024) << " МБ\n";
    std::cout << "⚡ Скорость: " << speed_mb_per_sec << " МБ/с\n";

    return 0;
}
