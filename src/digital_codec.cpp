#include "digital_codec.h"

#include <cassert>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <sodium.h>

namespace digitalcodec {

static inline int64_t ipow2(int n) { return (int64_t)1 << n; }

void DigitalCodec::configure(const CodecParams &params) {
    if (params.bitsM <= 0 || params.bitsM > 31) {
        throw std::invalid_argument("bitsM must be in 1..31");
    }
    if (params.bitsQ <= 0 || params.bitsQ > 16) {
        throw std::invalid_argument("bitsQ must be in 1..16");
    }
    if (params.funType < 1 || params.funType > 5) {
        throw std::invalid_argument("funType must be 1..5");
    }
    params_ = params;
    cols_ = (params_.funType == 5) ? 4 : 3;
    coeff_.clear();
    reset();
}

void DigitalCodec::loadCoefficientsCSV(const std::string &csvPath) {
    if (cols_ == 0) {
        throw std::logic_error("configure() before loadCoefficientsCSV()");
    }
    std::ifstream in(csvPath);
    if (!in) throw std::runtime_error("Failed to open coefficients CSV: " + csvPath);

    coeff_.clear();
    std::string line;
    while (std::getline(in, line)) {
        // Skip empty/comment lines
        bool allspace = true;
        for (char c : line) { if (!std::isspace((unsigned char)c)) { allspace = false; break; } }
        if (allspace) continue;
        if (!line.empty() && line[0] == '#') continue;

        std::vector<int32_t> row;
        row.reserve(cols_);
        std::stringstream ss(line);
        std::string cell;
        while (std::getline(ss, cell, ',')) {
            // allow semicolon-separated as well
            size_t pos = cell.find(';');
            if (pos != std::string::npos) cell = cell.substr(0, pos);
            // trim spaces
            size_t b = cell.find_first_not_of(" \t");
            size_t e = cell.find_last_not_of(" \t");
            std::string token = (b == std::string::npos) ? std::string() : cell.substr(b, e - b + 1);
            if (token.empty()) continue;
            long long v = std::stoll(token);
            row.push_back(static_cast<int32_t>(v));
        }
        if (!row.empty()) {
            if ((int)row.size() != cols_) {
                throw std::runtime_error("CSV row has wrong number of columns");
            }
            coeff_.push_back(std::move(row));
        }
    }
    const size_t expectedRows = static_cast<size_t>(ipow2(params_.bitsQ));
    if (coeff_.size() != expectedRows) {
        throw std::runtime_error("CSV rows != 2^Q");
    }
}

void DigitalCodec::reset() {
    enc_h1_ = wrapM(params_.h1);
    enc_h2_ = wrapM(params_.h2);
    dec_h1_ = enc_h1_;
    dec_h2_ = enc_h2_;
    resetDebugStats();
    if (params_.debugMode) {
        std::cout << "🔄 [Codec] Состояния инициализированы: enc_h1_=" << enc_h1_
                  << ", enc_h2_=" << enc_h2_ << ", dec_h1_=" << dec_h1_
                  << ", dec_h2_=" << dec_h2_ << std::endl;
    }
}

void DigitalCodec::syncStates(int32_t h1, int32_t h2) {
    enc_h1_ = wrapM(h1);
    enc_h2_ = wrapM(h2);
    dec_h1_ = enc_h1_;
    dec_h2_ = enc_h2_;
    if (params_.debugMode) {
        std::cout << "🔄 [Codec] Состояния синхронизированы: enc_h1_=" << enc_h1_
                  << ", enc_h2_=" << enc_h2_ << ", dec_h1_=" << dec_h1_
                  << ", dec_h2_=" << dec_h2_ << std::endl;
    }
}

int32_t DigitalCodec::wrapM(int64_t v) const {
    const int64_t mod = ipow2(params_.bitsM);
    int64_t r = v % mod;
    if (r < 0) r += mod;
    // convert to signed two's complement range
    int64_t signBit = ipow2(params_.bitsM - 1);
    if (r >= signBit) r -= mod;
    return static_cast<int32_t>(r);
}

int DigitalCodec::bytesPerSymbol() const {
    return (params_.bitsM + 7) / 8;  // Round up: M=8->1, M=9..16->2, M=17..24->3, M=25..31->4
}

void DigitalCodec::toBytes(int32_t v, std::vector<uint8_t>& out) const {
    // Store as two's complement in little-endian byte order
    const int numBytes = bytesPerSymbol();
    uint32_t mod = static_cast<uint32_t>(ipow2(params_.bitsM));
    uint32_t u = static_cast<uint32_t>(v) & (mod - 1);
    
    for (int i = 0; i < numBytes; ++i) {
        out.push_back(static_cast<uint8_t>(u & 0xFF));
        u >>= 8;
    }
}

int32_t DigitalCodec::fromBytes(const uint8_t* data) const {
    const int numBytes = bytesPerSymbol();
    uint32_t val = 0;
    
    // Read in little-endian byte order
    for (int i = 0; i < numBytes; ++i) {
        val |= static_cast<uint32_t>(data[i]) << (8 * i);
    }
    
    // Mask to M bits
    if (params_.bitsM < 32) {
        uint32_t mask = (1u << params_.bitsM) - 1u;
        val &= mask;
    }
    
    // Sign-extend from M bits
    uint32_t signBit = 1u << (params_.bitsM - 1);
    if (val & signBit) {
        uint32_t mod = 1u << params_.bitsM;
        int32_t s = static_cast<int32_t>(val) - static_cast<int32_t>(mod);
        return s;
    }
    return static_cast<int32_t>(val);
}

int32_t DigitalCodec::digitalCodingFun(int funcIndex1Based, int32_t x, int32_t y) const {
    assert(funcIndex1Based >= 1);
    int idx = funcIndex1Based - 1;
    const auto &row = coeff_.at(static_cast<size_t>(idx));
    const int32_t a = row[0];
    const int32_t b = row[1];
    const int32_t q = row[2];

    auto mul = [&](int64_t lhs, int64_t rhs) { return wrapM(lhs * rhs); };
    auto add = [&](int64_t lhs, int64_t rhs) { return wrapM(lhs + rhs); };

    switch (params_.funType) {
        case 1: // a*x + b*y + q
            return add(add(mul(a, x), mul(b, y)), q);
        case 2: // a*x^2 + b*y + q
            return add(add(mul(a, mul(x, x)), mul(b, y)), q);
        case 3: // a*x^2 + b*y^2 + q
            return add(add(mul(a, mul(x, x)), mul(b, mul(y, y))), q);
        case 4: // a*x^3 + b*y^2 + q
            return add(add(mul(a, mul(mul(x, x), x)), mul(b, mul(y, y))), q);
        case 5: { // a*x + b*x*y + c*y + q
            const int32_t c = row[2];
            const int32_t q5 = row[3];
            return add(add(add(mul(a, x), mul(b, mul(x, y))), mul(c, y)), q5);
        }
        default:
            return 0;
    }
}

std::vector<uint8_t> DigitalCodec::encodeBytes(const std::vector<uint8_t> &input) {
    // Interpret each input byte as an information symbol in range [0..2^Q-1].
    // WARNING: This will lose data if input bytes are outside [0..2^Q-1]!
    // For arbitrary byte data, use encodeMessage() instead.
    const int maxSym = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(input.size() + 2);

    for (uint8_t symByte : input) {
        int sym = static_cast<int>(symByte);
        if (sym >= maxSym) {
            std::cerr << "⚠️  encodeBytes: symbol " << sym << " exceeds maxSym " << maxSym << ", clamping to 0\n";
            sym = 0; // or could use % maxSym
        }

        // two previous states
        int32_t x = enc_h1_;
        int32_t y = enc_h2_;

        // function index in MATLAB is 1-based: II = data(INF) + 1
        int funcIndex = sym + 1;

        int32_t next = digitalCodingFun(funcIndex, x, y);

        // shift states
        enc_h2_ = enc_h1_;
        enc_h1_ = next;

        toBytes(next, out);
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::decodeBytes(const std::vector<uint8_t> &coded) {
    // Best-effort inverse assuming unique mapping (no collisions, no skips)
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    const int bps = bytesPerSymbol();
    std::vector<uint8_t> out;
    out.reserve(coded.size() / bps);

    for (size_t i = 0; i + bps <= coded.size(); i += bps) {
        int32_t observed = fromBytes(&coded[i]);

        int32_t x = dec_h1_;
        int32_t y = dec_h2_;

        int matched = -1;
        for (int ff = 1; ff <= funCount; ++ff) {
            int32_t result = digitalCodingFun(ff, x, y);
            if (result == observed) { 
                matched = ff - 1; 
                break; 
            }
        }
        if (matched < 0) {
            // cannot decode deterministically; emit 0 and continue
            matched = 0;
        }

        // update states with the same rule as encoder
        int32_t next = observed;
        dec_h2_ = dec_h1_;
        dec_h1_ = next;

        out.push_back(static_cast<uint8_t>(matched));
    }
    return out;
}

// === High-level message API ===
std::vector<uint8_t> DigitalCodec::packBytesToSymbols(const std::vector<uint8_t> &input) const {
    const int q = params_.bitsQ;
    const uint32_t mask = (1u << q) - 1u;
    std::vector<uint8_t> symbols;
    symbols.reserve((input.size() * 8 + q - 1) / q);
    uint32_t bitbuf = 0;
    int bitcount = 0;
    for (uint8_t b : input) {
        bitbuf |= (uint32_t)b << bitcount;
        bitcount += 8;
        while (bitcount >= q) {
            uint8_t sym = static_cast<uint8_t>(bitbuf & mask);
            symbols.push_back(sym);
            bitbuf >>= q;
            bitcount -= q;
        }
    }
    if (bitcount > 0) {
        uint8_t sym = static_cast<uint8_t>(bitbuf & mask);
        symbols.push_back(sym);
    }
    return symbols;
}

std::vector<uint8_t> DigitalCodec::unpackSymbolsToBytes(const std::vector<uint8_t> &symbols, size_t expected_len) const {
    const int q = params_.bitsQ;
    std::vector<uint8_t> out;
    out.reserve(expected_len);
    uint32_t bitbuf = 0;
    int bitcount = 0;
    for (uint8_t sym : symbols) {
        bitbuf |= ((uint32_t)sym) << bitcount;
        bitcount += q;
        while (bitcount >= 8) {
            uint8_t byte = static_cast<uint8_t>(bitbuf & 0xFFu);
            out.push_back(byte);
            bitbuf >>= 8;
            bitcount -= 8;
            if (out.size() == expected_len) return out;
        }
    }
    if (out.size() < expected_len && bitcount > 0) {
        uint8_t byte = static_cast<uint8_t>(bitbuf & 0xFFu);
        out.push_back(byte);
    }
    if (out.size() > expected_len) out.resize(expected_len);
    return out;
}

std::vector<uint8_t> DigitalCodec::encodeSymbols(const std::vector<uint8_t> &symbols) {
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(symbols.size());
    
    for (uint8_t symByte : symbols) {
        int sym = static_cast<int>(symByte);
        if (sym >= funCount) {
            std::cerr << "❌ encodeSymbols: symbol " << sym << " >= funCount " << funCount << "!\n";
            sym = sym % funCount;
        }
        
        if (params_.statsMode) {
            metrics_encoded_symbols_.fetch_add(1, std::memory_order_relaxed);
        }
        
        int32_t x = enc_h1_;
        int32_t y = enc_h2_;
        if (params_.debugMode) {
            std::cout << "🔍 [Encode] Символ=" << sym << " (II=" << (sym + 1)
                      << "), h1=" << x << ", h2=" << y << std::endl;
        }
        
        // MATLAB: Вычисляем все функции для проверки коллизий
        std::vector<int32_t> RR(funCount);
        for (int ff = 0; ff < funCount; ++ff) {
            RR[ff] = digitalCodingFun(ff + 1, x, y);
        }
        
        // MATLAB: Проверяем наличие коллизий (unique)
        std::vector<int32_t> uniqueVals;
        std::vector<int> firstIndices;  // IA в MATLAB
        for (int ff = 0; ff < funCount; ++ff) {
            bool found = false;
            for (size_t u = 0; u < uniqueVals.size(); ++u) {
                if (RR[ff] == uniqueVals[u]) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                uniqueVals.push_back(RR[ff]);
                firstIndices.push_back(ff);
            }
        }
        
        int32_t next;
        bool skipSymbol = false;
        bool usedDirectInfo = false;
        const bool collisionDetected = (static_cast<int>(uniqueVals.size()) != funCount);
        std::string encode_reason = "уникальное отображение";
        
        // MATLAB: if length(CoderData) == FunCount
        if (!collisionDetected) {
            // Нет коллизий - кодируем нормально
            next = RR[sym];
            encode_reason = "без коллизий";
        } else {
            // Есть коллизии - определяем индексы дубликатов
            // DupData = setdiff(1:FunCount, IA);
            std::vector<int> dupIndices;
            for (int ff = 0; ff < funCount; ++ff) {
                bool isFirst = false;
                for (int idx : firstIndices) {
                    if (ff == idx) {
                        isFirst = true;
                        break;
                    }
                }
                if (!isFirst) {
                    dupIndices.push_back(ff);
                }
            }
            
            // MATLAB: if II < DupData (проверяем, что sym меньше всех дубликатов)
            bool symBeforeDups = true;
            for (int dupIdx : dupIndices) {
                if (sym >= dupIdx) {
                    symBeforeDups = false;
                    break;
                }
            }
            
            if (symBeforeDups) {
                next = RR[sym];
                encode_reason = "символ до дубликатов";
            } else {
                // MATLAB: InfoInsteadOfRand mode
                bool symInRR = false;
                for (int32_t val : RR) {
                    if ((sym + 1) == val) {  // sym+1 потому что II - это информационное состояние 1..FunCount
                        symInRR = true;
                        break;
                    }
                }
                
                if (!symInRR && params_.infoInsteadOfRand) {
                    // Прямая передача информационного значения
                    next = sym + 1;
                    usedDirectInfo = true;
                    encode_reason = "прямая передача информации";
                } else {
                    // MATLAB: Пропускаем символ, генерируем случайное значение
                    skipSymbol = true;
                    std::srand(static_cast<unsigned>(std::time(nullptr)) + sym);
                    int32_t minVal = -(1 << (params_.bitsM - 1));
                    int32_t maxVal = (1 << (params_.bitsM - 1)) - 1;
                    
                    do {
                        next = minVal + (std::rand() % (maxVal - minVal + 1));
                        
                        // Проверка: не равно ни одному из RR
                        bool inRR = false;
                        for (int32_t val : RR) {
                            if (next == val) {
                                inRR = true;
                                break;
                            }
                        }
                        if (inRR) continue;
                        
                        // Проверка: не равно информационным значениям (если InfoInsteadOfRand)
                        if (params_.infoInsteadOfRand && next >= 1 && next <= funCount) {
                            continue;
                        }
                        
                        break;
                    } while (true);
                    
                    std::cerr << "⚠️  Пропущен символ " << sym << " из-за коллизии (Nskip++)\n";
                    encode_reason = "случайное значение при коллизии";
                }
            }
        }
        
        if (params_.statsMode) {
            if (collisionDetected) {
                metrics_encode_collisions_.fetch_add(1, std::memory_order_relaxed);
            }
            if (skipSymbol) {
                metrics_encode_random_fallbacks_.fetch_add(1, std::memory_order_relaxed);
            }
            if (usedDirectInfo) {
                metrics_encode_direct_info_.fetch_add(1, std::memory_order_relaxed);
            }
        }
        
        // Обновляем состояния
        enc_h2_ = enc_h1_;
        enc_h1_ = next;
        
        if (params_.debugMode) {
            std::cout << "   ↳ [Encode] Результат=" << next << " (" << encode_reason << ")\n";
            if (skipSymbol) {
                std::cout << "   ⚠️ [Encode] Символ пропущен из-за дубликатов, передано случайное значение\n";
            }
        }
        
        // Записываем закодированное значение
        toBytes(next, out);
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::decodeSymbols(const std::vector<uint8_t> &coded) {
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    const int bps = bytesPerSymbol();
    std::vector<uint8_t> out;
    out.reserve(coded.size() / bps);
    
    for (size_t i = 0; i + bps <= coded.size(); i += bps) {
        int32_t observed = fromBytes(&coded[i]);
        int32_t x = dec_h1_;
        int32_t y = dec_h2_;
        bool decoded_symbol = false;
        bool decode_direct = false;
        bool decode_skip = false;
        
        // MATLAB: Вычисляем все функции
        std::vector<int32_t> RR(funCount);
        for (int ff = 0; ff < funCount; ++ff) {
            RR[ff] = digitalCodingFun(ff + 1, x, y);
        }
        
        if (params_.debugMode) {
            std::cout << "🔍 [Decode] Наблюдение=" << observed << ", h1=" << x << ", h2=" << y << std::endl;
        }
        
        // MATLAB: Ищем совпадение Iind = find(r(k) == RR)
        int matched = -1;
        for (int ff = 0; ff < funCount; ++ff) {
            if (RR[ff] == observed) {
                matched = ff;  // Берём первое совпадение
                break;
            }
        }
        
        if (matched >= 0) {
            // Найдено совпадение - декодируем символ
            int32_t next = observed;
            dec_h2_ = dec_h1_;
            dec_h1_ = next;
            out.push_back(static_cast<uint8_t>(matched));
            decoded_symbol = true;
            if (params_.debugMode) {
                std::cout << "   ↳ [Decode] Совпадение функции #" << (matched + 1)
                          << " -> символ " << matched << std::endl;
            }
        } else {
            // MATLAB: Проверяем прямую передачу информации
            // Iind = find(r(k) == 1:FunCount)
            if (params_.infoInsteadOfRand && observed >= 1 && observed <= funCount) {
                // Прямая передача информационного значения
                int32_t next = observed;
                dec_h2_ = dec_h1_;
                dec_h1_ = next;
                out.push_back(static_cast<uint8_t>(observed - 1));  // observed-1 для индексации от 0
                decoded_symbol = true;
                decode_direct = true;
                if (params_.debugMode) {
                    std::cout << "   ↳ [Decode] Прямая передача информации -> символ " << (observed - 1) << std::endl;
                }
            } else {
                // MATLAB: Пропускаем символ (Nskip++)
                // Обновляем состояния тем же значением
                int32_t next = observed;
                dec_h2_ = dec_h1_;
                dec_h1_ = next;
                // НЕ добавляем в out - это реализация пропуска символа
                std::cerr << "⚠️  Пропущен символ при декодировании (не найдено совпадение)";
                std::cerr << " [observed=" << observed << ", x=" << x << ", y=" << y << "]";
                std::cerr << " [RR=";
                for (int ff = 0; ff < funCount; ++ff) {
                    std::cerr << RR[ff];
                    if (ff < funCount - 1) std::cerr << ",";
                }
                std::cerr << "]\n";
                decode_skip = true;
                if (params_.debugMode) {
                    std::cout << "   ⚠️ [Decode] Символ пропущен: совпадение не найдено и InfoInsteadOfRand недоступен\n";
                }
            }
        }
        
        if (params_.statsMode) {
            if (decoded_symbol) {
                metrics_decoded_symbols_.fetch_add(1, std::memory_order_relaxed);
            }
            if (decode_direct) {
                metrics_decode_direct_info_.fetch_add(1, std::memory_order_relaxed);
            }
            if (decode_skip) {
                metrics_decode_skips_.fetch_add(1, std::memory_order_relaxed);
            }
        }
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::encodeMessage(const std::vector<uint8_t> &input, bool use_hash) {
    // States are maintained across messages for network communication
    
    std::vector<uint8_t> payload_to_encode;
    
    if (use_hash) {
        // Calculate SHA-256 hash of input data
        unsigned char hash[crypto_hash_sha256_BYTES];
        crypto_hash_sha256(hash, input.data(), input.size());
        
        // Prepend hash to data: [32 bytes hash] + [data]
        payload_to_encode.reserve(crypto_hash_sha256_BYTES + input.size());
        payload_to_encode.insert(payload_to_encode.end(), hash, hash + crypto_hash_sha256_BYTES);
        payload_to_encode.insert(payload_to_encode.end(), input.begin(), input.end());
    } else {
        payload_to_encode = input;
    }
    
    // Frame: [len(2 bytes little endian)] [encoded symbols]
    const size_t len = payload_to_encode.size();
    std::vector<uint8_t> symbols = packBytesToSymbols(payload_to_encode);
    std::vector<uint8_t> coded = encodeSymbols(symbols);
    std::vector<uint8_t> framed;
    framed.reserve(2 + coded.size());
    framed.push_back(static_cast<uint8_t>(len & 0xFF));
    framed.push_back(static_cast<uint8_t>((len >> 8) & 0xFF));
    framed.insert(framed.end(), coded.begin(), coded.end());
    return framed;
}

std::vector<uint8_t> DigitalCodec::decodeMessage(const std::vector<uint8_t> &coded, size_t expected_len, bool use_hash) {
    // States are maintained across messages for network communication
    if (coded.size() < 2) return {};
    size_t len = (size_t)coded[0] | ((size_t)coded[1] << 8);
    if (expected_len != 0) len = expected_len;
    std::vector<uint8_t> payload(coded.begin() + 2, coded.end());
    std::vector<uint8_t> symbols = decodeSymbols(payload);
    std::vector<uint8_t> decoded_bytes = unpackSymbolsToBytes(symbols, len);
    
    if (use_hash) {
        // Verify hash integrity
        if (decoded_bytes.size() < crypto_hash_sha256_BYTES) {
            std::cerr << "❌ Декодированный буфер слишком мал для проверки хеша!\n";
            std::cerr << "   Получено: " << decoded_bytes.size() << " байт, ожидалось минимум: " 
                      << crypto_hash_sha256_BYTES << " байт (SHA-256)\n";
            std::cerr << "   Возможные причины: повреждение данных, несовпадение параметров кодека (M/Q/CSV)\n";
            return {};
        }
        
        // Extract received hash (first 32 bytes)
        unsigned char received_hash[crypto_hash_sha256_BYTES];
        std::memcpy(received_hash, decoded_bytes.data(), crypto_hash_sha256_BYTES);
        
        // Calculate actual hash of the data (after hash)
        size_t data_len = decoded_bytes.size() - crypto_hash_sha256_BYTES;
        unsigned char actual_hash[crypto_hash_sha256_BYTES];
        crypto_hash_sha256(actual_hash, decoded_bytes.data() + crypto_hash_sha256_BYTES, data_len);
        
        // Return only the data part (without hash)
        std::vector<uint8_t> result(decoded_bytes.begin() + crypto_hash_sha256_BYTES, decoded_bytes.end());
        
        // Compare hashes
        if (std::memcmp(received_hash, actual_hash, crypto_hash_sha256_BYTES) != 0) {
            std::cerr << "⚠️  Хеш не совпадает в decodeMessage — данные могут быть повреждены!\n";
            // Возвращаем данные несмотря на несовпадение хеша (для отладки)
        }
        
        return result;
    }
    
    return decoded_bytes;
}

void DigitalCodec::resetDebugStats() const {
    metrics_encoded_symbols_.store(0, std::memory_order_relaxed);
    metrics_encode_collisions_.store(0, std::memory_order_relaxed);
    metrics_encode_random_fallbacks_.store(0, std::memory_order_relaxed);
    metrics_encode_direct_info_.store(0, std::memory_order_relaxed);
    metrics_decoded_symbols_.store(0, std::memory_order_relaxed);
    metrics_decode_direct_info_.store(0, std::memory_order_relaxed);
    metrics_decode_skips_.store(0, std::memory_order_relaxed);
}

void DigitalCodec::printDebugStats(const std::string &context) const {
    if (!params_.statsMode) {
        return;
    }
    const std::string header = context.empty() ? "📊 Статистика цифрового кодека" : context;
    std::cout << header << "\n"
              << "   🔢 Закодировано символов: " << metrics_encoded_symbols_.load(std::memory_order_relaxed) << "\n"
              << "   ⚠️  Коллизий обнаружено: " << metrics_encode_collisions_.load(std::memory_order_relaxed) << "\n"
              << "   🎲 Случайных подстановок: " << metrics_encode_random_fallbacks_.load(std::memory_order_relaxed) << "\n"
              << "   📡 Прямых передач Info: " << metrics_encode_direct_info_.load(std::memory_order_relaxed) << "\n"
              << "   ✅ Декодировано символов: " << metrics_decoded_symbols_.load(std::memory_order_relaxed) << "\n"
              << "   ℹ️  Декодировано через Info: " << metrics_decode_direct_info_.load(std::memory_order_relaxed) << "\n"
              << "   ⛔ Пропусков при декодировании: " << metrics_decode_skips_.load(std::memory_order_relaxed) << "\n";
}

} // namespace digitalcodec



