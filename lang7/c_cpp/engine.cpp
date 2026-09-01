// ============================================================================
// engine.cpp — 七语言协同 · C++17 引擎 (lang7)
//
// 在 C 核心 (entangle_core.c) 之上做 C++17 封装：
//   * 调用 AArch64/x86-64 汇编内核 ec_pairmix_asm（配对质量度量）
//   * 计算浓度/深度，产出叠加态 JSON 报告（供 Python 编排器 ctypes 调用）
//   * 提供 extern "C" 桥：engine_entangle() / engine_free()
//   * 独立 CLI：entangle-cc A.pdf B.pdf --seed 34
//
// 铁律：浓度 ≥ 34%（阿雷纳常数）；深度趋于 99.99%。
// ============================================================================
#include "entangle_core.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

#define EC_ARENA 0.34

extern "C" uint64_t ec_pairmix_asm(const uint8_t* pa, const uint8_t* pb, size_t n)
    __attribute__((weak));
// 弱符号回退：无汇编时用 C 参考
extern "C" uint64_t ec_pairmix_asm_fallback(const uint8_t* pa, const uint8_t* pb, size_t n) {
    uint64_t s = 0;
    for (size_t i = 0; i < n; ++i) {
        int d = (int)pa[i] - (int)pb[i];
        s += (uint64_t)(d < 0 ? -d : d);
    }
    return s;
}

static std::string sha256_hex(const std::string& data);  // 简易 SHA-256（自包含）

// ---------------- JSON 助手 ----------------
static void json_str(std::ostringstream& o, const char* k, const std::string& v) {
    o << "\"" << k << "\":\"";
    for (char c : v) {
        if (c == '"' || c == '\\') o << '\\';
        o << c;
    }
    o << "\",";
}
static void json_num(std::ostringstream& o, const char* k, double v) {
    o << "\"" << k << "\":" << std::fixed << std::setprecision(10) << v << ",";
}

struct EngineOut {
    std::string json;
    std::string shareA, shareB;
    std::string err;
};

static EngineOut engineRun(const std::string& pathA, const std::string& pathB,
                           uint64_t seed, double thetaFix, int roundsFix,
                           double fid, int depthRounds) {
    EngineOut out;
    auto slurp = [](const std::string& p, bool& ok) {
        std::ifstream f(p, std::ios::binary);
        if (!f) { ok = false; return std::string(); }
        std::ostringstream ss; ss << f.rdbuf(); ok = true;
        return ss.str();
    };
    bool okA = false, okB = false;
    std::string A = slurp(pathA, okA), B = slurp(pathB, okB);
    if (!okA || !okB) {
        out.err = "cannot read inputs";
        out.json = "{\"err\":\"cannot read inputs\"}";
        return out;
    }

    const uint8_t* a = (const uint8_t*)A.data();
    const uint8_t* b = (const uint8_t*)B.data();
    size_t na = A.size(), nb = B.size();

    // 秩配对（C 核心）
    size_t n = na > nb ? na : nb;
    std::vector<uint32_t> permA(n), permB(n);
    ec_rank_pair(a, na, b, nb, permA.data(), permB.data());

    // 优化：θ=π/2（最大纠缠门）+ 二分补轮次至浓度 ≥ 34%
    double theta = thetaFix >= 0 ? thetaFix : 1.5707963267948966;
    int rounds = roundsFix > 0 ? roundsFix : 8;
    double conc = ec_concentration(a, na, b, nb, theta, rounds, fid);
    while (conc < EC_ARENA - 1e-9 && rounds < 512) {
        ++rounds;
        conc = ec_concentration(a, na, b, nb, theta, rounds, fid);
    }
    if (conc < EC_ARENA - 1e-9) {
        out.err = "concentration < 34% unreachable";
        out.json = "{\"err\":\"concentration < 34% unreachable\"}";
        return out;
    }

    // 深度（趋于 99.99%）
    double netD = 0, rawD = 0, selF = 0;
    bool depthOk = depthRounds > 0 &&
        ec_depth_metrics(a, na, b, nb, theta, depthRounds, &netD, &rawD, &selF) != 0;

    // EPR 共享
    out.shareA.assign(na, 0);
    out.shareB.assign(nb, 0);
    ec_epr_shares(seed, a, na, b, nb, permA.data(), permB.data(),
                  (uint8_t*)out.shareA.data(), (uint8_t*)out.shareB.data());

    // 汇编内核 + C 参考对照（自校验）
    std::vector<uint8_t> pa(n), pb(n);
    for (size_t i = 0; i < n; ++i) {
        pa[i] = a[permA[i] % na];
        pb[i] = b[permB[i] % nb];
    }
    uint64_t mixAsm = ec_pairmix_asm
        ? ec_pairmix_asm(pa.data(), pb.data(), n)
        : ec_pairmix_asm_fallback(pa.data(), pb.data(), n);
    uint64_t mixC = ec_pairmix_c(a, na, b, nb, permA.data(), permB.data());
    bool mixMatch = (mixAsm == mixC);

    // CRC / 哈希
    uint16_t crcA = ec_crc16((const uint8_t*)out.shareA.data(), na, 0xFFFF);
    uint16_t crcB = ec_crc16((const uint8_t*)out.shareB.data(), nb, 0xFFFF);
    std::string shaA = sha256_hex(A), shaB = sha256_hex(B);

    // JSON 报告
    std::ostringstream o;
    o << "{";
    json_num(o, "conc", conc);
    json_num(o, "theta", theta);
    json_num(o, "rounds", (double)rounds);
    json_num(o, "fid", fid);
    json_num(o, "netDepth", netD);
    json_num(o, "rawDepth", rawD);
    json_num(o, "selFrac", selF);
    json_num(o, "depthRounds", (double)(depthRounds > 0 ? depthRounds : 0));
    json_num(o, "n", (double)n);
    json_num(o, "seed", (double)seed);
    json_num(o, "pairmixAsm", (double)mixAsm);
    json_num(o, "pairmixC", (double)mixC);
    json_num(o, "crcA", (double)crcA);
    json_num(o, "crcB", (double)crcB);
    json_str(o, "shaA", shaA);
    json_str(o, "shaB", shaB);
    json_str(o, "depthOk", depthOk ? "1" : "0");
    json_str(o, "mixMatch", mixMatch ? "1" : "0");
    json_str(o, "err", "");
    // 去掉末尾逗号
    std::string j = o.str();
    if (!j.empty() && j.back() == ',') j.pop_back();
    j += "}";
    out.json = j;
    return out;
}

// ============================ extern "C" 桥（Python ctypes 调用） ===========
extern "C" {
char* engine_entangle(const char* pathA, const char* pathB,
                      uint64_t seed, double thetaFix, int roundsFix,
                      double fid, int depthRounds, char** shareA,
                      size_t* lenA, char** shareB, size_t* lenB) {
    EngineOut r = engineRun(pathA ? pathA : "", pathB ? pathB : "",
                            seed, thetaFix, roundsFix, fid, depthRounds);
    char* json = (char*)malloc(r.json.size() + 1);
    if (!json) return nullptr;
    memcpy(json, r.json.c_str(), r.json.size() + 1);
    if (shareA) {
        *shareA = (char*)malloc(r.shareA.size() ? r.shareA.size() : 1);
        if (*shareA && !r.shareA.empty())
            memcpy(*shareA, r.shareA.data(), r.shareA.size());
        if (lenA) *lenA = r.shareA.size();
    }
    if (shareB) {
        *shareB = (char*)malloc(r.shareB.size() ? r.shareB.size() : 1);
        if (*shareB && !r.shareB.empty())
            memcpy(*shareB, r.shareB.data(), r.shareB.size());
        if (lenB) *lenB = r.shareB.size();
    }
    return json;
}
void engine_free(void* p) { free(p); }
}

// ============================ CLI =========================================
int main(int argc, char** argv) {
    if (argc < 3) {
        std::fprintf(stderr,
            "用法: entangle-cc <A.pdf> <B.pdf> [--seed N] [--theta R] "
            "[--rounds K] [--fidelity D] [--depth-rounds R]\n");
        return 1;
    }
    std::string a = argv[1], b = argv[2];
    uint64_t seed = 34;
    double theta = -1; int rounds = -1; double fid = 0.9; int depthR = 16384;
    for (int i = 3; i + 1 < argc; i += 2) {
        std::string k = argv[i];
        if (k == "--seed") seed = strtoull(argv[i+1], nullptr, 10);
        else if (k == "--theta") theta = atof(argv[i+1]);
        else if (k == "--rounds") rounds = atoi(argv[i+1]);
        else if (k == "--fidelity") fid = atof(argv[i+1]);
        else if (k == "--depth-rounds") depthR = atoi(argv[i+1]);
    }
    EngineOut r = engineRun(a, b, seed, theta, rounds, fid, depthR);
    if (!r.err.empty()) { std::fprintf(stderr, "error: %s\n", r.err.c_str()); return 1; }
    std::printf("%s\n", r.json.c_str());
    return 0;
}

// ==================== 自包含 SHA-256（FIPS 180-4）=========================
static std::string sha256_hex(const std::string& data) {
    uint32_t h[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                     0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    auto rotr = [](uint32_t x, int n2) { return (x >> n2) | (x << (32 - n2)); };
    uint64_t len = data.size();
    std::string m = data;
    m += (char)0x80;
    while (m.size() % 64 != 56) m += (char)0;
    for (int i = 7; i >= 0; --i) m += (char)((len * 8) >> (8 * i));
    for (size_t off = 0; off < m.size(); off += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = ((uint32_t)(uint8_t)m[off+i*4] << 24) | ((uint32_t)(uint8_t)m[off+i*4+1] << 16) |
                   ((uint32_t)(uint8_t)m[off+i*4+2] << 8) | (uint32_t)(uint8_t)m[off+i*4+3];
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3);
            uint32_t s1 = rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10);
            w[i] = w[i-16]+s0+w[i-7]+s1;
        }
        uint32_t a0=h[0],b0=h[1],c0=h[2],d0=h[3],e0=h[4],f0=h[5],g0=h[6],h0=h[7];
        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = rotr(e0,6)^rotr(e0,11)^rotr(e0,25);
            uint32_t ch = (e0&f0)^((~e0)&g0);
            uint32_t t1 = h0+S1+ch+K[i]+w[i];
            uint32_t S0 = rotr(a0,2)^rotr(a0,13)^rotr(a0,22);
            uint32_t maj = (a0&b0)^(a0&c0)^(b0&c0);
            uint32_t t2 = S0+maj;
            h0=g0; g0=f0; f0=e0; e0=d0+t1; d0=c0; c0=b0; b0=a0; a0=t1+t2;
        }
        h[0]+=a0; h[1]+=b0; h[2]+=c0; h[3]+=d0; h[4]+=e0; h[5]+=f0; h[6]+=g0; h[7]+=h0;
    }
    static const char* hex = "0123456789abcdef";
    std::string out;
    for (int i = 0; i < 8; ++i)
        for (int j = 3; j >= 0; --j) {
            uint8_t v = (uint8_t)(h[i] >> (8*j));
            out += hex[v >> 4]; out += hex[v & 15];
        }
    return out;
}
