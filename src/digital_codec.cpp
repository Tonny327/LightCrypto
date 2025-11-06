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
    errors_corrected_h_ = 0;
    errors_corrected_v_ = 0;
    // Отладочный вывод закомментирован для чистого вывода (как в LibSodium)
    // std::cout << "🔄 Состояния кодека инициализированы: enc_h1_=" << enc_h1_ 
    //           << ", enc_h2_=" << enc_h2_ << ", dec_h1_=" << dec_h1_ 
    //           << ", dec_h2_=" << dec_h2_ << std::endl;
}

void DigitalCodec::syncStates(int32_t h1, int32_t h2) {
    enc_h1_ = wrapM(h1);
    enc_h2_ = wrapM(h2);
    dec_h1_ = enc_h1_;
    dec_h2_ = enc_h2_;
    // Отладочный вывод закомментирован для чистого вывода (как в LibSodium)
    // std::cout << "🔄 Состояния синхронизированы: enc_h1_=" << enc_h1_ 
    //           << ", enc_h2_=" << enc_h2_ << ", dec_h1_=" << dec_h1_ 
    //           << ", dec_h2_=" << dec_h2_ << std::endl;
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

// BitChange: invert bit at position pos (1-based, like MATLAB)
int32_t DigitalCodec::bitChange(int32_t x, int pos) {
    if (pos < 1 || pos > 32) return x;
    int bitPos = pos - 1;  // convert to 0-based
    int32_t mask = 1 << bitPos;
    return x ^ mask;  // XOR flips the bit
}

// AllCodeFun: compute all coding functions for given arguments
std::vector<int32_t> DigitalCodec::allCodeFun(int32_t x, int32_t y) const {
    const int N = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<int32_t> R;
    R.reserve(N);
    
    for (int k = 1; k <= N; ++k) {
        R.push_back(digitalCodingFun(k, x, y));
    }
    
    return R;
}

// Decode11ext: extended decoding with error hypothesis checking
std::pair<std::vector<int32_t>, int32_t> DigitalCodec::decode11ext(
    int32_t h1, int32_t h2, int32_t h, int32_t v, int flag) const {
    
    std::vector<int32_t> I;
    int32_t pos = 0;
    const int Q = params_.bitsQ;
    
    // Проверка гипотезы об ОТСУТСТВИИ ошибки в обоих блоках пары [h_k, v_k]
    if (flag == 0) {
        std::vector<int32_t> RR = allCodeFun(h1, h2);
        std::vector<int32_t> RRv = allCodeFun(h, h1);
        
        // Find indices where RR == h
        std::vector<int32_t> indh;
        for (size_t i = 0; i < RR.size(); ++i) {
            if (RR[i] == h) {
                indh.push_back(static_cast<int32_t>(i + 1));  // 1-based index
            }
        }
        
        // Find indices where RRv == v
        std::vector<int32_t> indv;
        for (size_t i = 0; i < RRv.size(); ++i) {
            if (RRv[i] == v) {
                indv.push_back(static_cast<int32_t>(i + 1));  // 1-based index
            }
        }
        
        // Intersection (avoid duplicates)
        for (int32_t ih : indh) {
            for (int32_t iv : indv) {
                if (ih == iv) {
                    // Check if already in I
                    bool found = false;
                    for (int32_t val : I) {
                        if (val == ih) {
                            found = true;
                            break;
                        }
                    }
                    if (!found) {
                        I.push_back(ih);
                    }
                }
            }
        }
    }
    
    // Декодирование для случая поражения h_k из пары [h_k, v_k]
    if (flag == 1) {
        std::vector<int32_t> RR = allCodeFun(h1, h2);
        
        // Try each bit position
        for (int k = 1; k <= Q; ++k) {
            int32_t tmp = bitChange(h, k);  // гипотеза о корректном состоянии h
            
            // Find indices where RR == tmp
            std::vector<int32_t> indh;
            for (size_t i = 0; i < RR.size(); ++i) {
                if (RR[i] == tmp) {
                    indh.push_back(static_cast<int32_t>(i + 1));  // 1-based
                }
            }
            
            // Compute RRv with corrected h
            std::vector<int32_t> RRv = allCodeFun(tmp, h1);
            
            // Find indices where RRv == v
            std::vector<int32_t> indv;
            for (size_t i = 0; i < RRv.size(); ++i) {
                if (RRv[i] == v) {
                    indv.push_back(static_cast<int32_t>(i + 1));  // 1-based
                }
            }
            
            // Intersection
            if (!indh.empty() && !indv.empty()) {
                for (int32_t ih : indh) {
                    for (int32_t iv : indv) {
                        if (ih == iv) {
                            I.push_back(ih);
                            pos = k;
                            break;
                        }
                    }
                    if (pos > 0) break;
                }
                if (pos > 0) break;
            }
        }
    }
    
    // Декодирование для случая поражения v_k из пары [h_k, v_k]
    if (flag == 2) {
        std::vector<int32_t> RR = allCodeFun(h1, h2);
        
        // Find indices where RR == h (h is not corrupted)
        std::vector<int32_t> indh;
        for (size_t i = 0; i < RR.size(); ++i) {
            if (RR[i] == h) {
                indh.push_back(static_cast<int32_t>(i + 1));  // 1-based
            }
        }
        
        std::vector<int32_t> RRv = allCodeFun(h, h1);
        
        // Try each bit position in v
        for (int k = 1; k <= Q; ++k) {
            int32_t tmp = bitChange(v, k);  // гипотеза об истинном состоянии v
            
            // Find indices where RRv == tmp
            std::vector<int32_t> indv;
            for (size_t i = 0; i < RRv.size(); ++i) {
                if (RRv[i] == tmp) {
                    indv.push_back(static_cast<int32_t>(i + 1));  // 1-based
                }
            }
            
            // Intersection
            if (!indv.empty()) {
                for (int32_t ih : indh) {
                    for (int32_t iv : indv) {
                        if (ih == iv) {
                            I.push_back(ih);
                            pos = k;
                            break;
                        }
                    }
                    if (pos > 0) break;
                }
                if (pos > 0) break;
            }
        }
    }
    
    return std::make_pair(I, pos);
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
    // 1-1 encoding scheme: each symbol produces [h, v] block pair
    // MATLAB: sig(2*BL - 1) = h, sig(2*BL) = v
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(symbols.size() * 2 * bytesPerSymbol());  // Each symbol produces 2 blocks
    
    for (uint8_t symByte : symbols) {
        int sym = static_cast<int>(symByte);
        if (sym >= funCount) {
            std::cerr << "❌ encodeSymbols: symbol " << sym << " >= funCount " << funCount << "!\n";
            sym = sym % funCount;
        }
        
        // MATLAB: II = INF(BL) (1-based index)
        int II = sym + 1;  // Convert to 1-based
        
        // MATLAB: x = sig(2*BL - 2) = v(k-1) = enc_h1_
        //         y = sig(2*BL - 3) = h(k-1) = enc_h2_
        int32_t x = enc_h1_;  // v(k-1)
        int32_t y = enc_h2_;  // h(k-1)
        
        // MATLAB: RR = AllCodeFun([x y], COEFF, FunType)
        std::vector<int32_t> RR = allCodeFun(x, y);
        
        // MATLAB: sig(2*BL - 1) = RR(II)  -> h block
        int32_t h = RR[II - 1];  // II is 1-based, RR is 0-based
        
        // MATLAB: x = sig(2*BL - 1) = h
        //         y = sig(2*BL - 2) = v(k-1) = enc_h1_
        x = h;
        y = enc_h1_;  // v(k-1)
        
        // MATLAB: RRv = AllCodeFun([x y], COEFF, FunType)
        std::vector<int32_t> RRv = allCodeFun(x, y);
        
        // MATLAB: sig(2*BL) = RRv(II)  -> v block
        int32_t v = RRv[II - 1];  // II is 1-based, RRv is 0-based
        
        // Write [h, v] block pair
        toBytes(h, out);
        toBytes(v, out);
        
        // Update states for next block: h1 = v(k), h2 = h(k)
        enc_h2_ = h;  // h(k) -> h2 (for next block: h2 = h(k-1))
        enc_h1_ = v;  // v(k) -> h1 (for next block: h1 = v(k-1))
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::decodeSymbols(const std::vector<uint8_t> &coded) {
    // 1-1 decoding scheme: each [h, v] block pair decodes to one symbol
    // Uses Decode11ext with hypothesis checking for error correction
    const int bps = bytesPerSymbol();
    std::vector<uint8_t> out;
    out.reserve(coded.size() / (2 * bps));  // Each symbol is encoded as 2 blocks
    
    // Process blocks in pairs [h, v]
    for (size_t i = 0; i + 2 * bps <= coded.size(); i += 2 * bps) {
        // Read h and v blocks
        int32_t h = fromBytes(&coded[i]);
        int32_t v = fromBytes(&coded[i + bps]);
        
        // MATLAB: h1 = rr(2*BL - 2) = v(k-1) = dec_h1_
        //         h2 = rr(2*BL - 3) = h(k-1) = dec_h2_
        int32_t h1 = dec_h1_;  // v(k-1)
        int32_t h2 = dec_h2_;  // h(k-1)
        
        int errPosDec = 0;  // 0 = no error, 1 = error in h, 2 = error in v
        std::vector<int32_t> I_;
        int32_t ePos = 0;
        
        // 1. Проверка гипотезы «ОШИБКА ОТСУТСТВУЕТ»
        auto result = decode11ext(h1, h2, h, v, 0);
        I_ = result.first;
        ePos = result.second;
        
        if (I_.empty()) {
            errPosDec = 1;  // переход к гипотезе «ошибка в H»
            if (params_.debugMode) {
                std::cout << "🔍 [Отладка] Гипотеза 0: ошибка обнаружена, переходим к проверке блока h\n";
            }
        } else {
            // Декодированное значение при отсутствии ошибок
            int32_t decodedIdx = I_[0] - 1;  // Convert 1-based to 0-based
            if (decodedIdx >= 0 && decodedIdx < static_cast<int32_t>(ipow2(params_.bitsQ))) {
                out.push_back(static_cast<uint8_t>(decodedIdx));
            }
            if (params_.debugMode) {
                std::cout << "🔍 [Отладка] Гипотеза 0: ошибок не обнаружено, декодировано: " << decodedIdx << "\n";
            }
        }
        
        // 2. Проверка гипотезы «ОШИБКА в СУББЛОКЕ H»
        if (errPosDec == 1) {
            result = decode11ext(h1, h2, h, v, 1);
            I_ = result.first;
            ePos = result.second;
            
            if (I_.empty()) {
                errPosDec = 2;  // переход к гипотезе «ошибка в V»
                if (params_.debugMode) {
                    std::cout << "🔍 [Отладка] Гипотеза 1: ошибка в h не подтверждена, переходим к проверке блока v\n";
                }
            } else {
                int32_t decodedIdx = I_[0] - 1;  // Convert 1-based to 0-based
                if (decodedIdx >= 0 && decodedIdx < static_cast<int32_t>(ipow2(params_.bitsQ))) {
                    out.push_back(static_cast<uint8_t>(decodedIdx));
                }
                if (params_.debugMode) {
                    std::cout << "🔍 [Отладка] Гипотеза 1: ошибка в h обнаружена, позиция бита: " << ePos 
                              << ", декодировано: " << decodedIdx << "\n";
                }
            }
        }
        
        // 3. Проверка гипотезы «ОШИБКА в СУББЛОКЕ V»
        if (errPosDec == 2) {
            result = decode11ext(h1, h2, h, v, 2);
            I_ = result.first;
            ePos = result.second;
            
            if (!I_.empty()) {
                int32_t decodedIdx = I_[0] - 1;  // Convert 1-based to 0-based
                if (decodedIdx >= 0 && decodedIdx < static_cast<int32_t>(ipow2(params_.bitsQ))) {
                    out.push_back(static_cast<uint8_t>(decodedIdx));
                }
                if (params_.debugMode) {
                    std::cout << "🔍 [Отладка] Гипотеза 2: ошибка в v обнаружена, позиция бита: " << ePos 
                              << ", декодировано: " << decodedIdx << "\n";
                }
            } else {
                if (params_.debugMode) {
                    std::cout << "🔍 [Отладка] Гипотеза 2: ошибка в v не подтверждена, позиция не найдена\n";
                }
            }
        }
        
        // ИСПРАВЛЕНИЕ ОШИБКИ в СИГНАЛЕ
        // исправление в h:
        if (errPosDec == 1 && ePos > 0) {
            int32_t h_before = h;
            h = bitChange(h, ePos);
            errors_corrected_h_++;
            std::cout << "🔧 [Помехоустойчивость] Обнаружена и исправлена ошибка в блоке h: "
                      << "бит " << ePos << " инвертирован (было: " << h_before 
                      << ", стало: " << h << ")\n";
        } else if (errPosDec == 1 && ePos == 0 && params_.debugMode) {
            std::cout << "⚠️  [Отладка] Ошибка в блоке h обнаружена, но позиция бита не найдена (не удалось исправить)\n";
        }
        // исправление в v:
        if (errPosDec == 2 && ePos > 0) {
            int32_t v_before = v;
            v = bitChange(v, ePos);
            errors_corrected_v_++;
            std::cout << "🔧 [Помехоустойчивость] Обнаружена и исправлена ошибка в блоке v: "
                      << "бит " << ePos << " инвертирован (было: " << v_before 
                      << ", стало: " << v << ")\n";
        } else if (errPosDec == 2 && ePos == 0 && params_.debugMode) {
            std::cout << "⚠️  [Отладка] Ошибка в блоке v обнаружена, но позиция бита не найдена (не удалось исправить)\n";
        }
        
        // Обновление состояний декодера для следующего блока
        // После декодирования: h1 = v(k), h2 = h(k)
        dec_h2_ = h;  // h(k) -> h2 (for next block: h2 = h(k-1))
        dec_h1_ = v;  // v(k) -> h1 (for next block: h1 = v(k-1))
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

} // namespace digitalcodec



