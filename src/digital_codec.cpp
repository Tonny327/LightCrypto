#include "digital_codec.h"

#include <cassert>
#include <cctype>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>

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

uint8_t DigitalCodec::toByte(int32_t v) const {
    // store as two's complement lower M bits
    uint32_t mod = static_cast<uint32_t>(ipow2(params_.bitsM));
    uint32_t u = static_cast<uint32_t>(v) & (mod - 1);
    return static_cast<uint8_t>(u);
}

int32_t DigitalCodec::fromByte(uint8_t b) const {
    uint32_t val = b;
    if (params_.bitsM < 8) {
        val &= (1u << params_.bitsM) - 1u;
    }
    // sign-extend
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
    const int maxSym = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(input.size() + 2);

    for (uint8_t symByte : input) {
        int sym = static_cast<int>(symByte) % maxSym; // clamp to [0..2^Q-1]

        // two previous states
        int32_t x = enc_h1_;
        int32_t y = enc_h2_;

        // function index in MATLAB is 1-based: II = data(INF) + 1
        int funcIndex = sym + 1;

        int32_t next = digitalCodingFun(funcIndex, x, y);

        // shift states
        enc_h2_ = enc_h1_;
        enc_h1_ = next;

        out.push_back(toByte(next));
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::decodeBytes(const std::vector<uint8_t> &coded) {
    // Best-effort inverse assuming unique mapping (no collisions, no skips)
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(coded.size());

    std::cerr << "🔍 Декодер: получено " << coded.size() << " байт, состояния: " << dec_h1_ << "," << dec_h2_ << "\n";

    for (size_t i = 0; i < coded.size(); ++i) {
        uint8_t b = coded[i];
        int32_t observed = fromByte(b);

        int32_t x = dec_h1_;
        int32_t y = dec_h2_;

        std::cerr << "🔍 Байт " << i << ": " << (int)b << " -> " << observed << ", состояния: " << x << "," << y << "\n";

        int matched = -1;
        for (int ff = 1; ff <= funCount; ++ff) {
            int32_t result = digitalCodingFun(ff, x, y);
            std::cerr << "  f(" << ff << "," << x << "," << y << ") = " << result << "\n";
            if (result == observed) { 
                matched = ff - 1; 
                std::cerr << "  ✅ Найдено совпадение: f(" << ff << ") = " << result << "\n";
                break; 
            }
        }
        if (matched < 0) {
            // cannot decode deterministically; emit 0 and continue
            matched = 0;
            std::cerr << "⚠️  Декодер: не найдено совпадение для байта " << (int)b 
                      << " (наблюдаемое: " << observed << ", состояния: " << x << "," << y << ")\n";
        }

        // update states with the same rule as encoder
        int32_t next = observed;
        dec_h2_ = dec_h1_;
        dec_h1_ = next;

        out.push_back(static_cast<uint8_t>(matched));
        std::cerr << "  📤 Декодированный символ: " << matched << "\n";
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
    const int maxSym = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(symbols.size());
    for (uint8_t symByte : symbols) {
        int sym = static_cast<int>(symByte) % maxSym;
        int32_t x = enc_h1_;
        int32_t y = enc_h2_;
        int funcIndex = sym + 1;
        int32_t next = digitalCodingFun(funcIndex, x, y);
        enc_h2_ = enc_h1_;
        enc_h1_ = next;
        out.push_back(toByte(next));
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::decodeSymbols(const std::vector<uint8_t> &coded) {
    const int funCount = static_cast<int>(ipow2(params_.bitsQ));
    std::vector<uint8_t> out;
    out.reserve(coded.size());
    for (uint8_t b : coded) {
        int32_t observed = fromByte(b);
        int32_t x = dec_h1_;
        int32_t y = dec_h2_;
        int matched = -1;
        for (int ff = 1; ff <= funCount; ++ff) {
            if (digitalCodingFun(ff, x, y) == observed) { matched = ff - 1; break; }
        }
        if (matched < 0) matched = 0;
        int32_t next = observed;
        dec_h2_ = dec_h1_;
        dec_h1_ = next;
        out.push_back(static_cast<uint8_t>(matched));
    }
    return out;
}

std::vector<uint8_t> DigitalCodec::encodeMessage(const std::vector<uint8_t> &input) {
    // Reset states per message for determinism
    reset();
    // Frame: [len(2 bytes little endian)] [encoded symbols]
    const size_t len = input.size();
    std::vector<uint8_t> symbols = packBytesToSymbols(input);
    std::vector<uint8_t> coded = encodeSymbols(symbols);
    std::vector<uint8_t> framed;
    framed.reserve(2 + coded.size());
    framed.push_back(static_cast<uint8_t>(len & 0xFF));
    framed.push_back(static_cast<uint8_t>((len >> 8) & 0xFF));
    framed.insert(framed.end(), coded.begin(), coded.end());
    return framed;
}

std::vector<uint8_t> DigitalCodec::decodeMessage(const std::vector<uint8_t> &coded, size_t expected_len) {
    // Reset states per message for determinism
    reset();
    if (coded.size() < 2) return {};
    size_t len = (size_t)coded[0] | ((size_t)coded[1] << 8);
    if (expected_len != 0) len = expected_len;
    std::vector<uint8_t> payload(coded.begin() + 2, coded.end());
    std::vector<uint8_t> symbols = decodeSymbols(payload);
    std::vector<uint8_t> bytes = unpackSymbolsToBytes(symbols, len);
    return bytes;
}

} // namespace digitalcodec



