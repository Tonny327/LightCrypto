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
    bool infoInsteadOfRand = true;  // MATLAB InfoInsteadOfRand mode for collision handling
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
    void syncStates(int32_t h1, int32_t h2);

    // Encode raw bytes into coded bytes using the digital coding scheme.
    // Supports any M up to 31. Each state is serialized using bytesPerSymbol() bytes.
    std::vector<uint8_t> encodeBytes(const std::vector<uint8_t> &input);

    // Decode coded bytes back to original (best-effort, assumes no skips and collision-free coefficients)
    std::vector<uint8_t> decodeBytes(const std::vector<uint8_t> &coded);

    // Encode full message: packs input bytes into Q-bit symbols, then encodes symbols
    // If use_hash=true, prepends SHA-256 hash for integrity check
    // Default: false (for MATLAB compatibility - collision handling is enough)
    std::vector<uint8_t> encodeMessage(const std::vector<uint8_t> &input, bool use_hash = false);
    // Decode full message: decodes symbols, then unpacks back to bytes (expected_len required)
    // If use_hash=true, verifies SHA-256 hash and returns empty vector on mismatch
    // Default: false (for MATLAB compatibility)
    std::vector<uint8_t> decodeMessage(const std::vector<uint8_t> &coded, size_t expected_len, bool use_hash = false);

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

    // Serialize/deserialize one M-bit signed value to bytes (supports any M up to 31)
    void toBytes(int32_t v, std::vector<uint8_t>& out) const;  // append bytes in little-endian
    int32_t fromBytes(const uint8_t* data) const;              // read bytes and sign-extend
    int bytesPerSymbol() const;                                // number of bytes needed for M bits

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



