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
#include <unordered_set>
#include <unordered_map>
#include <random>

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
    // Оптимизация для частого случая M=8
    if (params_.bitsM == 8) {
        return static_cast<int8_t>(static_cast<uint8_t>(v));
    }
    
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
    // Оптимизация для частого случая M=8 (1 байт)
    if (params_.bitsM == 8) {
        out.push_back(static_cast<uint8_t>(v));
        return;
    }
    
    // Store as two's complement in little-endian byte order
    const int numBytes = bytesPerSymbol();
    uint32_t mod = static_cast<uint32_t>(ipow2(params_.bitsM));
    uint32_t u = static_cast<uint32_t>(v) & (mod - 1);
    
    // Оптимизация: резервируем место заранее если возможно
    const size_t old_size = out.size();
    out.resize(old_size + numBytes);
    uint8_t* ptr = out.data() + old_size;
    
    for (int i = 0; i < numBytes; ++i) {
        ptr[i] = static_cast<uint8_t>(u & 0xFF);
        u >>= 8;
    }
}

int32_t DigitalCodec::fromBytes(const uint8_t* data) const {
    // Оптимизация для частого случая M=8 (1 байт)
    if (params_.bitsM == 8) {
        return static_cast<int8_t>(data[0]);
    }
    
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

    // Оптимизация для M=8: используем прямые операции без вызова wrapM
    if (params_.bitsM == 8) {
        auto mul8 = [](int32_t lhs, int32_t rhs) -> int32_t {
            return static_cast<int8_t>(static_cast<uint8_t>(lhs * rhs));
        };
        auto add8 = [](int32_t lhs, int32_t rhs) -> int32_t {
            return static_cast<int8_t>(static_cast<uint8_t>(lhs + rhs));
        };
        
        switch (params_.funType) {
            case 1: // a*x + b*y + q
                return add8(add8(mul8(a, x), mul8(b, y)), q);
            case 2: // a*x^2 + b*y + q
                return add8(add8(mul8(a, mul8(x, x)), mul8(b, y)), q);
            case 3: // a*x^2 + b*y^2 + q
                return add8(add8(mul8(a, mul8(x, x)), mul8(b, mul8(y, y))), q);
            case 4: // a*x^3 + b*y^2 + q
                return add8(add8(mul8(a, mul8(mul8(x, x), x)), mul8(b, mul8(y, y))), q);
            case 5: { // a*x + b*x*y + c*y + q
                const int32_t c = row[2];
                const int32_t q5 = row[3];
                return add8(add8(add8(mul8(a, x), mul8(b, mul8(x, y))), mul8(c, y)), q5);
            }
            default:
                return 0;
        }
    }
    
    // Общий случай для других M
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
    
    // Оптимизация для частого случая Q=2 (4 символа на байт)
    if (q == 2) {
        const size_t estimated_size = input.size() * 4;
        std::vector<uint8_t> symbols;
        symbols.reserve(estimated_size);
        const uint32_t mask = 0x3u; // 2 бита
        
        for (uint8_t b : input) {
            symbols.push_back(static_cast<uint8_t>(b & mask));
            symbols.push_back(static_cast<uint8_t>((b >> 2) & mask));
            symbols.push_back(static_cast<uint8_t>((b >> 4) & mask));
            symbols.push_back(static_cast<uint8_t>((b >> 6) & mask));
        }
        return symbols;
    }
    
    const uint32_t mask = (1u << q) - 1u;
    const size_t estimated_size = (input.size() * 8 + q - 1) / q;
    std::vector<uint8_t> symbols;
    symbols.reserve(estimated_size);
    uint32_t bitbuf = 0;
    int bitcount = 0;
    
    // Оптимизация: обрабатываем байты пакетно
    for (size_t i = 0; i < input.size(); ++i) {
        bitbuf |= (uint32_t)input[i] << bitcount;
        bitcount += 8;
        while (bitcount >= q) {
            symbols.push_back(static_cast<uint8_t>(bitbuf & mask));
            bitbuf >>= q;
            bitcount -= q;
        }
    }
    if (bitcount > 0) {
        symbols.push_back(static_cast<uint8_t>(bitbuf & mask));
    }
    return symbols;
}

std::vector<uint8_t> DigitalCodec::unpackSymbolsToBytes(const std::vector<uint8_t> &symbols, size_t expected_len) const {
    const int q = params_.bitsQ;
    
    // Оптимизация для частого случая Q=2 (4 символа на байт)
    if (q == 2) {
        std::vector<uint8_t> out;
        out.reserve(expected_len);
        
        // Обрабатываем все символы группами по 4, пока не достигнем expected_len
        for (size_t i = 0; i + 3 < symbols.size() && out.size() < expected_len; i += 4) {
            uint8_t byte = symbols[i] | (symbols[i+1] << 2) | (symbols[i+2] << 4) | (symbols[i+3] << 6);
            out.push_back(byte);
        }
        
        // Обработка остатка (если есть неполная группа из 4 символов)
        size_t processed = (out.size() * 4);
        if (processed < symbols.size() && out.size() < expected_len) {
            size_t remaining = symbols.size() - processed;
            uint8_t byte = 0;
            for (size_t i = 0; i < remaining && i < 4; ++i) {
                byte |= symbols[processed + i] << (i * 2);
            }
            out.push_back(byte);
        }
        
        // Обрезаем до expected_len если нужно
        if (out.size() > expected_len) {
            out.resize(expected_len);
        }
        return out;
    }
    
    std::vector<uint8_t> out;
    out.reserve(expected_len);
    uint32_t bitbuf = 0;
    int bitcount = 0;
    
    // Оптимизация: обрабатываем символы пакетно
    for (size_t i = 0; i < symbols.size() && out.size() < expected_len; ++i) {
        bitbuf |= ((uint32_t)symbols[i]) << bitcount;
        bitcount += q;
        while (bitcount >= 8 && out.size() < expected_len) {
            out.push_back(static_cast<uint8_t>(bitbuf & 0xFFu));
            bitbuf >>= 8;
            bitcount -= 8;
        }
    }
    if (out.size() < expected_len && bitcount > 0) {
        out.push_back(static_cast<uint8_t>(bitbuf & 0xFFu));
    }
    if (out.size() > expected_len) {
        out.resize(expected_len);
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::encodeSymbols(const std::vector<uint8_t> &symbols) {
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    const int bps = bytesPerSymbol();
    std::vector<uint8_t> out;
    out.reserve(symbols.size() * bps);
    
    // Для малых Q (<=4) используем простой массив, для больших - хеш-таблицы
    const bool useSimpleArray = (funCount <= 4);
    std::vector<int32_t> RR(funCount);
    
    // Для больших Q используем хеш-таблицы
    std::unordered_set<int32_t> rrSet;
    std::vector<bool> isFirstOccurrence;
    if (!useSimpleArray) {
        isFirstOccurrence.resize(funCount);
        rrSet.reserve(funCount);
    }
    
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
        
        // Вычисляем все функции
        for (int ff = 0; ff < funCount; ++ff) {
            RR[ff] = digitalCodingFun(ff + 1, x, y);
        }
        
        // Проверяем коллизии (оптимизировано для малых Q)
        bool collisionDetected = false;
        int minDupIdx = funCount;
        
        if (useSimpleArray) {
            // Для малых Q: простой линейный поиск (быстрее чем хеш-таблица для 4 элементов)
            for (int i = 0; i < funCount && !collisionDetected; ++i) {
                for (int j = i + 1; j < funCount; ++j) {
                    if (RR[i] == RR[j]) {
                        collisionDetected = true;
                        if (j < minDupIdx) minDupIdx = j;
                        break;
                    }
                }
            }
        } else {
            // Для больших Q: используем хеш-таблицу
            rrSet.clear();
            for (int ff = 0; ff < funCount; ++ff) {
                auto result = rrSet.insert(RR[ff]);
                if (!result.second) {
                    // Дубликат найден
                    collisionDetected = true;
                    if (ff < minDupIdx) minDupIdx = ff;
                }
            }
        }
        
        int32_t next;
        bool skipSymbol = false;
        bool usedDirectInfo = false;
        
        // Быстрый путь: нет коллизий (наиболее частый случай)
        if (!collisionDetected) {
            next = RR[sym];
        } else {
            // Есть коллизии - обрабатываем
            if (sym < minDupIdx) {
                next = RR[sym];
            } else {
                // Проверяем InfoInsteadOfRand режим
                int32_t directVal = sym + 1;
                bool directValInRR = false;
                if (useSimpleArray) {
                    for (int ff = 0; ff < funCount; ++ff) {
                        if (RR[ff] == directVal) {
                            directValInRR = true;
                            break;
                        }
                    }
                } else {
                    directValInRR = (rrSet.find(directVal) != rrSet.end());
                }
                
                if (!directValInRR && params_.infoInsteadOfRand) {
                    next = directVal;
                    usedDirectInfo = true;
                } else {
                    // Генерируем случайное значение
                    skipSymbol = true;
                    static thread_local std::mt19937 gen(std::random_device{}());
                    int32_t minVal = -(1 << (params_.bitsM - 1));
                    int32_t maxVal = (1 << (params_.bitsM - 1)) - 1;
                    std::uniform_int_distribution<int32_t> dist(minVal, maxVal);
                    
                    do {
                        next = dist(gen);
                        // Проверка: не равно ни одному из RR
                        bool inRR = false;
                        if (useSimpleArray) {
                            for (int ff = 0; ff < funCount; ++ff) {
                                if (RR[ff] == next) {
                                    inRR = true;
                                    break;
                                }
                            }
                        } else {
                            inRR = (rrSet.find(next) != rrSet.end());
                        }
                        
                        if (!inRR && (!params_.infoInsteadOfRand || next < 1 || next > funCount)) {
                            break;
                        }
                    } while (true);
                    
                    if (params_.debugMode) {
                        std::cerr << "⚠️  Пропущен символ " << sym << " из-за коллизии (Nskip++)\n";
                    }
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
            std::string encode_reason = collisionDetected ? "с коллизиями" : "без коллизий";
            if (usedDirectInfo) encode_reason = "прямая передача информации";
            if (skipSymbol) encode_reason = "случайное значение при коллизии";
            std::cout << "   ↳ [Encode] Результат=" << next << " (" << encode_reason << ")\n";
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
    
    // Для малых Q (<=4) используем простой линейный поиск, для больших - хеш-таблицу
    const bool useSimpleSearch = (funCount <= 4);
    std::vector<int32_t> RR(funCount);
    
    // Для больших Q используем хеш-таблицу
    std::unordered_map<int32_t, int> rrMap;
    if (!useSimpleSearch) {
        rrMap.reserve(funCount);
    }
    
    for (size_t i = 0; i + bps <= coded.size(); i += bps) {
        int32_t observed = fromBytes(&coded[i]);
        int32_t x = dec_h1_;
        int32_t y = dec_h2_;
        bool decoded_symbol = false;
        bool decode_direct = false;
        bool decode_skip = false;
        
        // Вычисляем все функции
        for (int ff = 0; ff < funCount; ++ff) {
            RR[ff] = digitalCodingFun(ff + 1, x, y);
        }
        
        if (params_.debugMode) {
            std::cout << "🔍 [Decode] Наблюдение=" << observed << ", h1=" << x << ", h2=" << y << std::endl;
        }
        
        // Поиск совпадения
        int matched = -1;
        
        if (useSimpleSearch) {
            // Для малых Q: простой линейный поиск (быстрее для 4 элементов)
            for (int ff = 0; ff < funCount; ++ff) {
                if (RR[ff] == observed) {
                    matched = ff;
                    break;
                }
            }
        } else {
            // Для больших Q: строим хеш-таблицу и ищем
            rrMap.clear();
            for (int ff = 0; ff < funCount; ++ff) {
                // Сохраняем только первое вхождение (как в оригинале)
                if (rrMap.find(RR[ff]) == rrMap.end()) {
                    rrMap[RR[ff]] = ff;
                }
            }
            auto it = rrMap.find(observed);
            if (it != rrMap.end()) {
                matched = it->second;
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
            // Проверяем прямую передачу информации
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
                // Пропускаем символ (Nskip++)
                int32_t next = observed;
                dec_h2_ = dec_h1_;
                dec_h1_ = next;
                // НЕ добавляем в out - это реализация пропуска символа
                if (params_.debugMode) {
                    std::cerr << "⚠️  Пропущен символ при декодировании (не найдено совпадение)";
                    std::cerr << " [observed=" << observed << ", x=" << x << ", y=" << y << "]\n";
                }
                decode_skip = true;
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
        // Оптимизация: избегаем копирования, используем ссылку где возможно
        payload_to_encode = input;
    }
    
    // Frame: [len(2 bytes little endian)] [encoded symbols]
    const size_t len = payload_to_encode.size();
    std::vector<uint8_t> symbols = packBytesToSymbols(payload_to_encode);
    std::vector<uint8_t> coded = encodeSymbols(symbols);
    
    // Оптимизация: резервируем место заранее и используем прямой доступ
    std::vector<uint8_t> framed;
    framed.reserve(2 + coded.size());
    framed.resize(2 + coded.size());
    framed[0] = static_cast<uint8_t>(len & 0xFF);
    framed[1] = static_cast<uint8_t>((len >> 8) & 0xFF);
    std::memcpy(framed.data() + 2, coded.data(), coded.size());
    return framed;
}

std::vector<uint8_t> DigitalCodec::decodeMessage(const std::vector<uint8_t> &coded, size_t expected_len, bool use_hash) {
    // States are maintained across messages for network communication
    if (coded.size() < 2) return {};
    size_t len = (size_t)coded[0] | ((size_t)coded[1] << 8);
    if (expected_len != 0) len = expected_len;
    
    // Оптимизация: создаем payload напрямую из данных без лишних копирований
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



