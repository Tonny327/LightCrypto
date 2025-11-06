#pragma once

#include <cstdint>
#include <string>
#include <utility>
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
    bool debugMode = false;  // Enable debug output for error detection/correction
    bool injectErrors = false;  // Enable artificial error injection for testing
    double errorRate = 0.01;  // Error injection rate (0.0 to 1.0) - probability of error per block
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
    
    // Get current encoder states
    int32_t get_enc_h1() const { return enc_h1_; }
    int32_t get_enc_h2() const { return enc_h2_; }
    
    // Get error correction statistics
    std::pair<size_t, size_t> get_error_stats() const { 
        return std::make_pair(errors_corrected_h_, errors_corrected_v_); 
    }
    void reset_error_stats() const { 
        errors_corrected_h_ = 0; 
        errors_corrected_v_ = 0; 
    }

    // Encode raw bytes into coded bytes using the digital coding scheme.
    // Supports any M up to 31. Each state is serialized using bytesPerSymbol() bytes.
    std::vector<uint8_t> encodeBytes(const std::vector<uint8_t> &input);

    // Decode coded bytes back to original (best-effort, assumes no skips and collision-free coefficients)
    std::vector<uint8_t> decodeBytes(const std::vector<uint8_t> &coded);

    // Encode full message: packs input bytes into Q-bit symbols, then encodes symbols
    // Uses 1-1 scheme: each symbol produces [h, v] block pair
    // If use_hash=true, prepends SHA-256 hash for integrity check
    // Default: false (for MATLAB compatibility - collision handling is enough)
    std::vector<uint8_t> encodeMessage(const std::vector<uint8_t> &input, bool use_hash = false);
    // Decode full message: decodes symbols using hypothesis checking, then unpacks back to bytes
    // Uses 1-1 scheme with error correction via Decode11ext
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

    // Compute all coding functions for given arguments (like AllCodeFun in MATLAB)
    // Returns vector of size 2^Q with all function results
    std::vector<int32_t> allCodeFun(int32_t x, int32_t y) const;

    // BitChange: invert bit at position pos (1-based, like MATLAB)
    static int32_t bitChange(int32_t x, int pos);

    // Decode11ext: extended decoding with error hypothesis checking
    // Returns pair: (decoded indices vector, error position)
    // flag: 0 = check for no error, 1 = error in h, 2 = error in v
    std::pair<std::vector<int32_t>, int32_t> decode11ext(
        int32_t h1, int32_t h2, int32_t h, int32_t v, int flag) const;

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
    // For 1-1 scheme: h1 = v(k-1), h2 = h(k-1)
    int32_t enc_h1_ = 0;  // v(k-1) for encoder
    int32_t enc_h2_ = 0;  // h(k-1) for encoder
    int32_t dec_h1_ = 0;  // v(k-1) for decoder
    int32_t dec_h2_ = 0;  // h(k-1) for decoder
    
    // Statistics for error correction
    mutable size_t errors_corrected_h_ = 0;  // errors corrected in h blocks
    mutable size_t errors_corrected_v_ = 0;  // errors corrected in v blocks
};

} // namespace digitalcodec



