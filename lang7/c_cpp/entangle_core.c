/* ============================================================================
 * entangle_core.c — 七语言协同 · C 核心实现 (lang7)
 * 纯 C11，零依赖。铁律：浓度 ≥ 34%，深度趋于 99.99%。
 * ========================================================================= */
#include "entangle_core.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define EC_PI 3.14159265358979323846
#define EC_ARENA 0.34        /* 阿雷纳常数 */
#define EC_DEPTH_TARGET 0.9999

/* ---------------- PRF ---------------- */
uint64_t ec_splitmix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ULL;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}
uint8_t ec_key_byte(uint64_t seed, uint64_t r) {
    uint64_t x = seed ^ (r * 0x9E3779B97F4A7C15ULL);
    return (uint8_t)(ec_splitmix64(x) >> 56);
}

/* ---------------- 秩配对 ---------------- */
/* 稳定计数排序（字节 0..255，同值按原索引升序）——O(n+256)，
 * 与 Rust/Python 孪生 (a[i % na], i) 的秩序完全一致。
 * period 为数组自身长度：虚拟值 bytes[i % period]（短数组周期化，避免越界）。 */
static void sort_perm(uint32_t* perm, const uint8_t* bytes, size_t period, size_t n) {
    size_t cnt[256] = {0};
    size_t start[256];
    size_t fill[256];
    size_t acc = 0, i;
    for (i = 0; i < n; ++i) cnt[bytes[i % period]]++;
    for (i = 0; i < 256; ++i) { start[i] = acc; acc += cnt[i]; }
    memcpy(fill, start, sizeof(fill));
    for (i = 0; i < n; ++i) {
        uint8_t v = bytes[i % period];
        perm[fill[v]++] = (uint32_t)i;
    }
}

size_t ec_rank_pair(const uint8_t* a, size_t na,
                    const uint8_t* b, size_t nb,
                    uint32_t* permA, uint32_t* permB) {
    size_t n = na > nb ? na : nb, i;
    if (n == 0) return 0;
    for (i = 0; i < n; ++i) { permA[i] = (uint32_t)i; permB[i] = (uint32_t)i; }
    sort_perm(permA, a, na, n);
    sort_perm(permB, b, nb, n);
    return n;
}

/* ---------------- 纠缠数学 ---------------- */
static double phi_of(uint8_t x) { return EC_PI * (double)x / 510.0; }

double ec_concurrence_xy(uint8_t x, uint8_t y, double theta) {
    double fa = phi_of(x), fb = phi_of(y);
    double cfa = cos(fa), sfa = sin(fa), cfb = cos(fb), sfb = sin(fb);
    double X = cfa * sfb, Y = sfa * cfb;
    double ad = (cfa * cfb) * (sfa * sfb);
    double c2 = cos(2.0 * theta), s2 = sin(2.0 * theta);
    double bg = X * Y * c2 + (Y * Y - X * X) * s2 * 0.5;
    return 2.0 * fabs(ad - bg);
}

double ec_one_round_prob(double C) {
    double v = 1.0 - C * C;
    return v <= 0.0 ? 1.0 : 1.0 - sqrt(v);
}

double ec_concentration(const uint8_t* a, size_t na,
                        const uint8_t* b, size_t nb,
                        double theta, int rounds, double fid) {
    size_t n = na > nb ? na : nb;
    if (n == 0) return 0.0;
    uint32_t* pa = (uint32_t*)malloc(n * sizeof(uint32_t));
    uint32_t* pb = (uint32_t*)malloc(n * sizeof(uint32_t));
    if (!pa || !pb) { free(pa); free(pb); return 0.0; }
    ec_rank_pair(a, na, b, nb, pa, pb);
    double c2 = cos(2.0 * theta), s2 = sin(2.0 * theta);
    double tot = 0.0;
    size_t i;
    for (i = 0; i < n; ++i) {
        uint8_t x = a[pa[i] % na], y = b[pb[i] % nb];
        double fa = phi_of(x), fb = phi_of(y);
        double cfa = cos(fa), sfa = sin(fa), cfb = cos(fb), sfb = sin(fb);
        double X = cfa * sfb, Y = sfa * cfb;
        double ad = (cfa * cfb) * (sfa * sfb);
        double bg = X * Y * c2 + (Y * Y - X * X) * s2 * 0.5;
        double C = 2.0 * fabs(ad - bg);
        double p = ec_one_round_prob(C);
        double fail = 1.0, dp = fid;
        int r;
        for (r = 1; r <= rounds; ++r, dp *= fid) {
            fail *= (1.0 - p * dp);
            if (fail < 1e-12) { fail = 0.0; break; }
        }
        tot += 1.0 - fail;
    }
    free(pa); free(pb);
    return tot / (double)n;
}

static int cmp_double_desc(const void* p, const void* q) {
    double d = *(const double*)p - *(const double*)q;
    return d > 0 ? -1 : (d < 0 ? 1 : 0);
}

int ec_depth_metrics(const uint8_t* a, size_t na,
                     const uint8_t* b, size_t nb,
                     double theta, int rounds,
                     double* netDepth, double* rawDepth, double* selFrac) {
    size_t n = na > nb ? na : nb;
    if (n == 0) return 0;
    uint32_t* pa = (uint32_t*)malloc(n * sizeof(uint32_t));
    uint32_t* pb = (uint32_t*)malloc(n * sizeof(uint32_t));
    double* s = (double*)malloc(n * sizeof(double));
    if (!pa || !pb || !s) { free(pa); free(pb); free(s); return 0; }
    ec_rank_pair(a, na, b, nb, pa, pb);
    double c2 = cos(2.0 * theta), s2 = sin(2.0 * theta);
    double rawSum = 0.0;
    size_t i;
    for (i = 0; i < n; ++i) {
        uint8_t x = a[pa[i] % na], y = b[pb[i] % nb];
        double fa = phi_of(x), fb = phi_of(y);
        double cfa = cos(fa), sfa = sin(fa), cfb = cos(fb), sfb = sin(fb);
        double X = cfa * sfb, Y = sfa * cfb;
        double ad = (cfa * cfb) * (sfa * sfb);
        double bg = X * Y * c2 + (Y * Y - X * X) * s2 * 0.5;
        double C = 2.0 * fabs(ad - bg);
        double p = ec_one_round_prob(C);
        s[i] = p <= 0.0 ? 0.0 : 1.0 - pow(1.0 - p, (double)rounds);
        rawSum += s[i];
    }
    *rawDepth = rawSum / (double)n;
    qsort(s, n, sizeof(double), cmp_double_desc);
    double cum = 0.0;
    size_t k = 0;
    for (i = 0; i < n; ++i) {
        cum += s[i];
        double mean = cum / (double)(i + 1);
        if (mean < EC_DEPTH_TARGET - 1e-12) { k = i; break; }
        k = i + 1;
    }
    if (k == 0) { free(pa); free(pb); free(s); return 0; }
    cum = 0.0;
    for (i = 0; i < k; ++i) cum += s[i];
    *netDepth = cum / (double)k;
    *selFrac = (double)k / (double)n;
    free(pa); free(pb); free(s);
    return (*netDepth >= EC_DEPTH_TARGET - 1e-12) ? 1 : 0;
}

/* ---------------- EPR 共享 ---------------- */
void ec_epr_shares(uint64_t seed,
                   const uint8_t* a, size_t na,
                   const uint8_t* b, size_t nb,
                   const uint32_t* permA, const uint32_t* permB,
                   uint8_t* shareA, uint8_t* shareB) {
    size_t n = na > nb ? na : nb, r;
    memset(shareA, 0, na);
    memset(shareB, 0, nb);
    for (r = 0; r < n; ++r) {
        uint8_t k = ec_key_byte(seed, (uint64_t)r);
        uint32_t ia = permA[r], ib = permB[r];
        if (ia < na) shareA[ia] = (uint8_t)(a[ia] ^ k);
        if (ib < nb) shareB[ib] = (uint8_t)(b[ib] ^ k);
    }
}

/* ---------------- CRC-16/CCITT-FALSE ---------------- */
uint16_t ec_crc16(const uint8_t* data, size_t n, uint16_t crc) {
    size_t i;
    for (i = 0; i < n; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        int j;
        for (j = 0; j < 8; ++j)
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

/* ---------------- 配对质量度量（C 参考） ---------------- */
uint64_t ec_pairmix_c(const uint8_t* a, size_t na,
                      const uint8_t* b, size_t nb,
                      const uint32_t* permA, const uint32_t* permB) {
    size_t n = na > nb ? na : nb, i;
    uint64_t sum = 0;
    for (i = 0; i < n; ++i) {
        int x = a[permA[i] % na], y = b[permB[i] % nb];
        int d = x - y;
        sum += (uint64_t)(d < 0 ? -d : d);
    }
    return sum;
}
