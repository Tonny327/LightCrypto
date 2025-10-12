#pragma once

#include <cstdint>
#include <string>
#include <vector>

// Lightweight C++ port of DigitalCodingFun and a minimal codec around it.
// The arithmetic is performed in a fixed-width signed M-bit ring (two's complement)
// with wrap-around semantics modulo 2^M.

namespace digitalcodec {

struct CodecParams {
    int bitsM = 8;           // word size (M)
    int bitsQ = 6;           // number of information bits per symbol (Q)
    int funType = 1;         // DigitalCodingFun variant 1..5
    int32_t h1 = 7;          // initial state 1
    int32_t h2 = 23;         // initial state 2
};

// COEFF is a matrix with rows = 2^Q, columns depend on funType
// For funType in {1,2,3,4}: 3 columns (a,b,q)
// For funType == 5: 4 columns (a,b,c,q)
class DigitalCodec {
public:
    DigitalCodec() = default;

    void configure(const CodecParams &params);

    // Load coefficients from simple CSV file.
    // Expected columns per row: funType 1..4 => 3 columns; funType 5 => 4 columns.
    // Number of rows must be exactly 2^Q. Whitespace is allowed.
    void loadCoefficientsCSV(const std::string &csvPath);

    // Reset internal generator states
    void reset();

    // Encode raw bytes into coded bytes using the digital coding scheme.
    // Assumes M <= 8 so each state is serialized as one byte (wrap to uint8_t).
    std::vector<uint8_t> encodeBytes(const std::vector<uint8_t> &input);

    // Decode coded bytes back to original (best-effort, assumes no skips and collision-free coefficients)
    std::vector<uint8_t> decodeBytes(const std::vector<uint8_t> &coded);

    // Encode full message: packs input bytes into Q-bit symbols, then encodes symbols
    // If use_hash=true, prepends SHA-256 hash for integrity check
    std::vector<uint8_t> encodeMessage(const std::vector<uint8_t> &input, bool use_hash = true);
    // Decode full message: decodes symbols, then unpacks back to bytes (expected_len required)
    // If use_hash=true, verifies SHA-256 hash and returns empty vector on mismatch
    std::vector<uint8_t> decodeMessage(const std::vector<uint8_t> &coded, size_t expected_len, bool use_hash = true);

private:
    // Helpers for symbol-level operation
    std::vector<uint8_t> packBytesToSymbols(const std::vector<uint8_t> &input) const;
    std::vector<uint8_t> unpackSymbolsToBytes(const std::vector<uint8_t> &symbols, size_t expected_len) const;
    std::vector<uint8_t> encodeSymbols(const std::vector<uint8_t> &symbols);
    std::vector<uint8_t> decodeSymbols(const std::vector<uint8_t> &coded);

    // Compute DigitalCodingFun for one function index (1-based like MATLAB), given previous states x,y
    int32_t digitalCodingFun(int funcIndex1Based, int32_t x, int32_t y) const;

    // Wrap signed integer to M-bit two's complement range [-(2^(M-1))..(2^(M-1)-1)]
    int32_t wrapM(int64_t v) const;

    // Serialize/deserialize one M-bit signed value to uint8_t buffer (M<=8)
    uint8_t toByte(int32_t v) const;       // two's complement cast
    int32_t fromByte(uint8_t b) const;     // sign-extend from M bits

private:
    CodecParams params_{};
    std::vector<std::vector<int32_t>> coeff_; // [2^Q][cols]
    int cols_ = 0;

    // rolling states for encode/decode
    int32_t enc_h1_ = 0;
    int32_t enc_h2_ = 0;
    int32_t dec_h1_ = 0;
    int32_t dec_h2_ = 0;
};

} // namespace digitalcodec



