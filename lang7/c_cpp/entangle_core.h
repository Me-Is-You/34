/* ============================================================================
 * entangle_core.h — 七语言协同 · C 核心 API (lang7)
 *
 * 与 entangle.cpp 同源的纠缠数学内核，写成纯 C11，供：
 *   C++ (engine.cpp 封装) / Rust (FFI 对照) / Python (ctypes) /
 *   汇编 (harness) / MicroPython (逻辑复用) / Verilog (golden vectors)
 * 共用。秩配对 + 布洛赫球映射 + Procrustean 浓缩 + 多轮蒸馏 + EPR 共享密钥。
 *
 * 铁律：浓度值不能低于 34%（阿雷纳常数）；深度趋于 99.99%。
 * ========================================================================= */
#ifndef ENTANGLE_CORE_H
#define ENTANGLE_CORE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- PRF（splitmix64）------------------------------------------------- */
uint64_t ec_splitmix64(uint64_t x);
uint8_t  ec_key_byte(uint64_t seed, uint64_t r);

/* ---- 秩配对 -------------------------------------------------------------
 * a/b 为两文件字节流；permA/permB 输出长度为 n = max(na,nb) 的排列
 * （permX[r] = 第 r 小字节在原数组中的索引，并列按索引序）。
 * 返回 n；permA/permB 须至少能容纳 n 个 uint32_t。 */
size_t ec_rank_pair(const uint8_t* a, size_t na,
                    const uint8_t* b, size_t nb,
                    uint32_t* permA, uint32_t* permB);

/* ---- 纠缠数学 -----------------------------------------------------------
 * 单对并发度与单轮浓缩成功概率；θ 为纠缠门角度（π/2 = 最大纠缠门）。 */
double ec_concurrence_xy(uint8_t x, uint8_t y, double theta);
double ec_one_round_prob(double C);

/* 全量纠缠浓度：conc(θ,R) = mean_i[ 1 − Π_{r=1..R}(1 − p_i·d^r) ]
 * a/b 为原字节流（内部先秩配对）。 */
double ec_concentration(const uint8_t* a, size_t na,
                        const uint8_t* b, size_t nb,
                        double theta, int rounds, double fid);

/* 深度指标（理想保真极限 d→1）：netDepth ≥ 99.99%、rawDepth、selFrac
 * 不可达（s_max < 99.99%）时返回 0。 */
int ec_depth_metrics(const uint8_t* a, size_t na,
                     const uint8_t* b, size_t nb,
                     double theta, int rounds,
                     double* netDepth, double* rawDepth, double* selFrac);

/* ---- EPR 共享密钥 --------------------------------------------------------
 * shareA/out：与 a 等长；shareB/out 与 b 等长（须预先分配）。
 * shareX[permX[r]] = 原字节 ⊕ K[r]，K[r] = ec_key_byte(seed, r)。 */
void ec_epr_shares(uint64_t seed,
                   const uint8_t* a, size_t na,
                   const uint8_t* b, size_t nb,
                   const uint32_t* permA, const uint32_t* permB,
                   uint8_t* shareA, uint8_t* shareB);

/* ---- 校验与信标 ----------------------------------------------------------
 * CRC-16/CCITT-FALSE：34 米信号波帧完整性（MicroPython/Verilog 同算法）。 */
uint16_t ec_crc16(const uint8_t* data, size_t n, uint16_t crc);

/* ---- 配对质量度量（汇编内核对照基准）------------------------------------
 * pairmix = Σ |a[permA[r]] − b[permB[r]]|  —— 秩配对后字节差之和。
 * 汇编版（lang7/asm）应与之逐位一致。 */
uint64_t ec_pairmix_c(const uint8_t* a, size_t na,
                      const uint8_t* b, size_t nb,
                      const uint32_t* permA, const uint32_t* permB);

#ifdef __cplusplus
}
#endif

#endif /* ENTANGLE_CORE_H */
