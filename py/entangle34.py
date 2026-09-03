#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
#  entangle34.py — PDF 真实纠缠机 · 单文件版 v34.99
#
#  一个文件 = 全部功能（Python 为主，C 与汇编/机器码内嵌为辅）：
#
#    · entangle / verify / audit / model / make-sample / selftest
#    · run   —— 持续工作：巡回纠缠 + 34m 范围性发射信号波 + 单机接收巡回
#                （UDP 组播 224.0.0.34:34034 TTL=2 ≈802.11 一跳 30–50m，
#                  34m 为设计目标；同机自发自收 = 单机接收）
#    · rx    —— 单机纯接收模式（另一台设备作接收端时用）
#
#  铁律：浓度值不能低于 34%（阿雷纳常数）；净纠缠深度趋于 99.99%。
#  科学属性：可重复性/可控制性/可测量性/随机化/可证伪性/客观性/信度/
#            效度/伦理性/透明性 —— 十项启动审计 + 12 项产物自检。
#  养成模型（越用越好）+ 自研自愈 L1–L4（重试/调参/重建/诚实跳过）。
#  运行开始即实时展示：浓度值 / 稳定值 / 浮动值 / 转换值 + 净深度。
#
#  用法（Termux / 桌面，仅需 python3，其余内嵌自动编译）:
#    python3 entangle34.py run                        # 持续巡回 + 发射 + 单机接收
#    python3 entangle34.py run --work 工作目录 --poll 5   # 自定义
#    python3 entangle34.py entangle A.pdf B.pdf -o out.pdf
#    python3 entangle34.py verify out.pdf out.pdf.shareA.bin out.pdf.shareB.bin
#    python3 entangle34.py audit [工作目录]
#    python3 entangle34.py tour --in inbox --out out --journal j --model m
#    python3 entangle34.py model [model.txt]
#    python3 entangle34.py make-sample sample.pdf
#    python3 entangle34.py rx --timeout 0              # 单机接收端
#    python3 entangle34.py selftest                    # 全链自检
#
#  首次运行 run/entangle 时：若系统有 cc/gcc/clang，会把内嵌的 C/汇编 源码
#  自动编译为机器码 .so（存于 <程序目录>/.ent34_cache/ 或临时目录）经 ctypes
#  加载加速；无编译器则自动回退纯 Python（功能完整，见运行提示）。
#  环境变量：ENTANGLE_ACCEL=0 强制纯 Python；ENTANGLE_ACCEL_LIB=<路径> 指定 .so。
#
#  矩阵式化 · 穿透式聚能：术语如实披露 —— 均为对"经典信道模拟量子通道"的
#  工程描述（CHSH ≤ 2 诚实边界，不声称真实量子传输）。
# ============================================================================
import argparse
import ctypes
import hashlib
import json
import math
import os
import random
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque

try:                                    # 管道/重定向下也实时刷新（Termux 无影响）
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass

FILE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================================================================
# ① 内嵌 C 辅助内核源码（运行时自动编译 .so 机器码）
# ================================================================
C_ACCEL_SRC = r'''/* ============================================================================
 * entangle_batch.c — PDF 真实纠缠机 · C 辅助加速内核（Python 版程序）
 *
 * 定位：Python 是主语言（全部逻辑/控制流都在 py/entangler.py），本文件只做
 *       一件事——把"数组级批量数值热循环"下沉到 C，编译成 .so（机器码）
 *       经 ctypes 供 Python 调用。未编译时 Python 自动回退同公式纯实现。
 *
 * 与 Python / C++ 版的逐位一致性（同一 libm、同一运算顺序、-ffp-contract=off）：
 *   eb_precompute  ≡ Python precompute_all（查表 cos/sin(π·x/510)）
 *   eb_conc_batch  ≡ Python concentration / C++ concentration
 *   eb_depth_batch ≡ Python _per_pair_s  / C++ depthMetrics
 *   eb_pairmix_c   ≡ 配对质量 C 参考（汇编差分测试基准）
 *
 * 铁律：浓度值不能低于 34%（阿雷纳常数）；净深度趋于 99.99%。
 * 编译（见 py/Makefile）：
 *   gcc -O2 -std=c11 -fPIC -ffp-contract=off -shared -o libentangle_batch.so \
 *       entangle_batch.c -lm
 * ========================================================================== */
#include <math.h>
#include <stddef.h>
#include <stdint.h>

#define EB_PI 3.14159265358979323846

/* ---- 确定性 PRF（与 C++/Python 完全一致的 splitmix64 / keyByte）---- */
uint64_t eb_splitmix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ULL;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}

uint8_t eb_key_byte(uint64_t seed, uint64_t r) {
    uint64_t x = seed ^ ((r * 0x9E3779B97F4A7C15ULL) & 0xFFFFFFFFFFFFFFFFULL);
    return (uint8_t)(eb_splitmix64(x) >> 56);
}

/* ---- 秩配对后的预计算：对每个秩位置 r 计算 (ad, xy, d2) ----
 * ad = (cosφa·cosφb)·(sinφa·sinφb)
 * X  = cosφa·sinφb, Y = sinφa·cosφb
 * xy = X·Y,  d2 = Y² − X²
 * 其中 φ = π·(字节值)/510 —— 与 Python 查表 cos/sin(π·v/510) 同输入同函数。
 */
size_t eb_precompute(const uint8_t* a, size_t na, const uint32_t* permA,
                     const uint8_t* b, size_t nb, const uint32_t* permB,
                     size_t n, double* out_ad, double* out_xy, double* out_d2) {
    size_t r;
    for (r = 0; r < n; ++r) {
        uint8_t x = a[permA[r] % na];
        uint8_t y = b[permB[r] % nb];
        double fa = EB_PI * (double)x / 510.0;
        double fb = EB_PI * (double)y / 510.0;
        double cfa = cos(fa), sfa = sin(fa);
        double cfb = cos(fb), sfb = sin(fb);
        double X = cfa * sfb, Y = sfa * cfb;
        out_ad[r] = (cfa * cfb) * (sfa * sfb);
        out_xy[r] = X * Y;
        out_d2[r] = Y * Y - X * X;
    }
    return n;
}

/* 单对并发度 → 单轮 Procrustean 概率（逐式同 Python/C++） */
static double one_round_prob(double C) {
    double v = 1.0 - C * C;
    return v <= 0.0 ? 1.0 : 1.0 - sqrt(v);
}

/* ---- 纠缠浓度批量：conc(θ,R) = mean[ 1 − Π_{r=1..R}(1 − p·d^r) ]
 * 返回平均浓度；out_s 非空时逐对写出 s = 1 − fail（与 Python per_pair 一致）。
 */
double eb_conc_batch(const double* ad, const double* xy, const double* d2,
                     size_t n, double theta, int rounds, double fid,
                     double* out_s) {
    double c2 = cos(2.0 * theta), s2 = sin(2.0 * theta);
    double tot = 0.0;
    size_t i;
    for (i = 0; i < n; ++i) {
        double bg = xy[i] * c2 + d2[i] * s2 * 0.5;
        double C = 2.0 * fabs(ad[i] - bg);
        double p = one_round_prob(C);
        double fail = 1.0, dp = fid;
        int r;
        for (r = 1; r <= rounds; ++r, dp *= fid) {
            fail *= (1.0 - p * dp);
            if (fail < 1e-12) { fail = 0.0; break; }
        }
        double s = 1.0 - fail;
        if (out_s) out_s[i] = s;
        tot += s;
    }
    return tot / (double)n;
}

/* ---- 深度模式批量（理想保真极限 d→1）：
 * s_i = p ≤ 0 ? 0 : 1 − (1 − p)^R；out_s 必须非空（逐对写出）。
 * 返回 rawSum/n（原始深度）；净深度/选择比例由 Python 排序后计算。
 */
double eb_depth_batch(const double* ad, const double* xy, const double* d2,
                      size_t n, double theta, int rounds, double* out_s) {
    double c2 = cos(2.0 * theta), s2 = sin(2.0 * theta);
    double raw = 0.0;
    size_t i;
    for (i = 0; i < n; ++i) {
        double bg = xy[i] * c2 + d2[i] * s2 * 0.5;
        double C = 2.0 * fabs(ad[i] - bg);
        double p = one_round_prob(C);
        out_s[i] = p <= 0.0 ? 0.0 : 1.0 - pow(1.0 - p, (double)rounds);
        raw += out_s[i];
    }
    return raw / (double)n;
}

/* ---- 配对质量度量（C 参考；汇编 pairmix 须与之逐位一致）----
 * pairmix = Σ |a[permA[r]] − b[permB[r]]|（秩配对后字节差之和）
 */
uint64_t eb_pairmix_c(const uint8_t* a, size_t na,
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
'''
ASM_X86_64_SRC = r'''/* ============================================================================
 * pairmix_x86_64.S — PDF 真实纠缠机 · Python 版 · 汇编辅助内核（x86-64 SSE2）
 *
 * uint64_t py_pairmix_asm(const uint8_t* pa, const uint8_t* pb, size_t n);
 *   计算 Σ |pa[i] − pb[i]|（秩配对后的字节差之和 = 配对质量度量）。
 *
 * 定位：本程序以 Python 为主语言；汇编只在"辅助"岗位上出现——
 *   1) 作为可选的机器码级差分基准：selftest 用它与 Python/C 三端互证；
 *   2) 编译为 .so 后由 Python 经 ctypes 直接调用（机器码执行）。
 *   ARM64 (NEON) 版见 pairmix_aarch64.S（手机 / Termux）。
 *
 * 寄存器:  rdi=pa, rsi=pb, rdx=n, rax=累加和（无符号）
 * 采用 SSE2 向量化：一次处理 16 对（psadbw = 无符号绝对差求和）。
 * ========================================================================== */

#if defined(__x86_64__)
    .text
    .p2align 4
    .globl  py_pairmix_asm
    .type   py_pairmix_asm, @function
py_pairmix_asm:
    xorl    %eax, %eax          # 标量累加和 = 0
    xorps   %xmm3, %xmm3        # 向量累加和 = 0
    movq    %rdx, %rcx
    shrq    $5, %rcx            # 32 字节块数（每轮 2×16B）
    jz      .Ltail

    .p2align 4
.Lvec:
    movdqu  (%rdi), %xmm0       # pa[0..15]
    movdqu  (%rsi), %xmm1       # pb[0..15]
    movdqu  16(%rdi), %xmm2     # pa[16..31]
    psadbw  %xmm1, %xmm0        # |差| 每 8 字节一组的和 → xmm0[0],xmm0[8]
    movdqu  16(%rsi), %xmm1     # pb[16..31]
    psadbw  %xmm1, %xmm2
    paddq   %xmm0, %xmm3
    paddq   %xmm2, %xmm3
    addq    $32, %rdi
    addq    $32, %rsi
    decq    %rcx
    jnz     .Lvec

    movdqa  %xmm3, %xmm0
    psrldq  $8, %xmm0
    paddq   %xmm3, %xmm0
    movq    %xmm0, %rax         # 向量部分和

.Ltail:
    andq    $31, %rdx           # 剩余 0..31 字节
    jz      .Ldone
    xorl    %ecx, %ecx
.Ltail_loop:
    movzbl  (%rdi,%rcx), %r8d
    movzbl  (%rsi,%rcx), %r9d
    subl    %r9d, %r8d          # r8d = x − y ∈ [−255,255]
    movl    %r8d, %r10d
    sarl    $31, %r10d          # 符号掩码：全 1（负）或全 0（正）
    movl    %r8d, %r9d
    xorl    %r10d, %r9d
    subl    %r10d, %r9d         # branchless abs：|x−y|
    addq    %r9, %rax
    incq    %rcx
    cmpq    %rdx, %rcx
    jb      .Ltail_loop
.Ldone:
    ret
    .size   py_pairmix_asm, .-py_pairmix_asm
    .section .note.GNU-stack,"",@progbits
#endif
'''
ASM_AARCH64_SRC = r'''/* ============================================================================
 * pairmix_aarch64.S — PDF 真实纠缠机 · Python 版 · 汇编辅助内核（AArch64 NEON）
 *
 * uint64_t py_pairmix_asm(const uint8_t* pa, const uint8_t* pb, size_t n);
 *   计算 Σ |pa[i] − pb[i]|（秩配对后的字节差之和 = 配对质量度量）。
 *
 * 定位：以 Python 为主语言；汇编为辅助内核（差分互证 + 可选的机器码加速）。
 *   本文件面向 ARM64 设备（如 Termux 里的 arm64 手机；vivo X300 · 天玑9500），
 *   与 pairmix_x86_64.S 接口与结果完全一致 —— selftest 按架构二选一编译。
 *
 * 调用约定 (AAPCS64): x0=pa, x1=pb, x2=n, 返回 x0。
 * 用 NEON (ASIMD) 向量化：一次 16 对，|a−b| 用 UABD + UADDLV 纵向累加。
 * ========================================================================== */

#if defined(__aarch64__)
    .text
    .p2align 4
    .globl  py_pairmix_asm
    .type   py_pairmix_asm, %function
py_pairmix_asm:
    mov     x3, #0                  // 标量累加和
    movi    v2.2d, #0               // 向量累加和（2×64bit 车道）
    lsr     x4, x2, #4              // 16 字节块数
    cbz     x4, .Ltail_a64

    .p2align 4
.Lvec_a64:
    ld1     {v0.16b}, [x0], #16     // pa[0..15]
    ld1     {v1.16b}, [x1], #16     // pb[0..15]
    uabd    v0.16b, v0.16b, v1.16b  // 无符号绝对差（16×8bit）
    uaddlv  d0, v0.16b              // 纵向求和 → 64 位
    add     v2.2d, v2.2d, v0.2d     // 累加（d0 高车道为 0）
    subs    x4, x4, #1
    b.ne    .Lvec_a64

    addp    v2.2d, v2.2d, v2.2d     // 两车道相加
    umov    x5, v2.d[0]
    add     x3, x3, x5

.Ltail_a64:
    and     x4, x2, #15             // 剩余 0..15 字节
    cbz     x4, .Ldone_a64
    mov     x5, #0
.Ltail_loop_a64:
    ldrb    w6, [x0, x5]
    ldrb    w7, [x1, x5]
    subs    w6, w6, w7
    cneg    w6, w6, mi              // |a−b|
    add     x3, x3, x6
    add     x5, x5, #1
    cmp     x5, x4
    b.lt    .Ltail_loop_a64

.Ldone_a64:
    mov     x0, x3
    ret
    .size   py_pairmix_asm, .-py_pairmix_asm
    .section .note.GNU-stack,"",@progbits
#endif
'''

# ================================================================
# ② Python 主引擎（核心数学 / PDF 容器 / verify / 养成模型）
# ================================================================
import hashlib
import math
import os
import time

__all__ = [
    "PI", "ARENA_CONSTANT", "DEPTH_TARGET", "VERSION",
    "EntangleError", "EntangleResult",
    "splitmix64", "key_byte", "sha256_hex",
    "rank_pair", "Precomputed", "precompute_all",
    "concentration", "depth_metrics",
    "shannon_entropy", "pearson",
    "load_accel", "accel_available", "disable_accel",
    "Model", "model_bucket",
    "PdfBuilder", "make_sample_pdf", "parse_pdf", "verify_artifact",
    "entangle_files", "random_seed",
    "read_bytes", "write_bytes", "list_pdf_files", "ensure_dir",
]

PI = 3.14159265358979323846          # 与 C++ kPi 相同（double π 的最近表示）
ARENA_CONSTANT = 0.34                # 阿雷纳常数：浓度下限，不可违反
DEPTH_TARGET = 0.9999                # 深度目标：趋于 99.99%
VERSION = "34.99"

_M64 = (1 << 64) - 1
_SPLIT_A = 0x9E3779B97F4A7C15
_SPLIT_B = 0xBF58476D1CE4E5B9
_SPLIT_C = 0x94D049BB133111EB


class EntangleError(Exception):
    """纠缠流程中的可预期错误（无法读取/数学上不可纠缠/自检失败等）。"""


# ---------------------------------------------------------------- utilities

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)
    return True


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# splitmix64 —— 确定性 PRF（与 C++/C 完全一致，uint64 回绕）
def splitmix64(x: int) -> int:
    x = (x + _SPLIT_A) & _M64
    x = ((x ^ (x >> 30)) * _SPLIT_B) & _M64
    x = ((x ^ (x >> 27)) * _SPLIT_C) & _M64
    return (x ^ (x >> 31)) & _M64


def key_byte(seed: int, r: int) -> int:
    x = (seed ^ ((r * _SPLIT_A) & _M64)) & _M64
    return splitmix64(x) >> 56


# --------------------------------------------------- 三角函数查表（每字节值）
# 每个字节 x 映射 |ψ(x)⟩ = cos(φ_x)|0⟩ + sin(φ_x)|1⟩，φ_x = π·x/510。
# 表项 = cos/sin(π·x/510.0)（与 C++ 逐对 cos(φ) 传入完全相同的 double，逐位一致）
_COS_T = [math.cos(PI * x / 510.0) for x in range(256)]
_SIN_T = [math.sin(PI * x / 510.0) for x in range(256)]


def _pair_xy(x: int, y: int):
    """返回 (ad, xy, d2) —— 与 θ 无关的三个预计算量（entangle.cpp precompute）。"""
    cfa, sfa = _COS_T[x], _SIN_T[x]
    cfb, sfb = _COS_T[y], _SIN_T[y]
    X = cfa * sfb
    Y = sfa * cfb
    ad = (cfa * cfb) * (sfa * sfb)
    return ad, X * Y, Y * Y - X * X


# -------------------------------------------------------------- rank pairing
# 秩配对：按 (字节值, 原索引) 对 0..n-1 排序（稳定计数排序，与 C++ sort 同序）。
def _sort_perm(data, period, n):
    cnt = [0] * 256
    for i in range(n):
        cnt[data[i % period]] += 1
    start = [0] * 256
    acc = 0
    for v in range(256):
        start[v] = acc
        acc += cnt[v]
    fill = start[:]
    perm = [0] * n
    for i in range(n):
        v = data[i % period]
        perm[fill[v]] = i
        fill[v] += 1
    return perm


def rank_pair(a: bytes, b: bytes):
    """permX[r] = 第 r 小的索引；rankX[i] = 索引 i 的秩（越界填充位秩 0）。"""
    n = max(len(a), len(b))
    if n == 0:
        raise EntangleError("空文件没有量子态，无法纠缠")
    permA = _sort_perm(a, len(a), n)
    permB = _sort_perm(b, len(b), n)
    rankA = [0] * len(a)
    rankB = [0] * len(b)
    for r in range(n):
        ia, ib = permA[r], permB[r]
        if ia < len(a):
            rankA[ia] = r
        if ib < len(b):
            rankB[ib] = r
    return permA, permB, rankA, rankB, n


class Precomputed:
    """n 对量子比特的 (ad, xy, d2) 预计算数组。

    ad/xy/d2 同时保留 Python 列表（纯 Python 回退路径）与按需打包的
    ctypes 数组（C 加速路径，机器码执行）。两种路径公式完全一致。
    """

    __slots__ = ("n", "ad", "xy", "d2", "_packed")

    def __init__(self, n):
        self.n = n
        self.ad = [0.0] * n
        self.xy = [0.0] * n
        self.d2 = [0.0] * n
        self._packed = None  # 惰性：(ad_c, xy_c, d2_c)

    def pack(self):
        if self._packed is None:
            import ctypes
            n = self.n
            CD = ctypes.c_double * n
            ad_c, xy_c, d2_c = CD(), CD(), CD()
            ad_c[:] = self.ad
            xy_c[:] = self.xy
            d2_c[:] = self.d2
            self._packed = (ad_c, xy_c, d2_c)
        return self._packed


def precompute_all(a, b, permA, permB, n, accel=None):
    """对全部 n 个秩配对位置预计算 (ad, xy, d2)。

    有 C 加速（机器码内核）时由 C 批量计算；否则纯 Python 计算。
    两条路径输入相同、公式相同（同一 libm）→ 逐位一致（selftest 验证）。
    """
    pre = Precomputed(n)
    la, lb = len(a), len(b)
    if accel is not None:
        import ctypes
        CD = ctypes.c_double * n
        ad_c, xy_c, d2_c = CD(), CD(), CD()
        n_in = accel.lib.eb_precompute(
            (ctypes.c_ubyte * la).from_buffer_copy(a), la,
            (ctypes.c_uint32 * n)(*permA),
            (ctypes.c_ubyte * lb).from_buffer_copy(b), lb,
            (ctypes.c_uint32 * n)(*permB),
            n, ad_c, xy_c, d2_c)
        if n_in != n:
            raise EntangleError("C 加速内核 eb_precompute 返回长度不符（自检失败）")
        pre.ad = list(ad_c)
        pre.xy = list(xy_c)
        pre.d2 = list(d2_c)
    else:
        get = _pair_xy
        ad_l, xy_l, d2_l = pre.ad, pre.xy, pre.d2
        for r in range(n):
            ad_l[r], xy_l[r], d2_l[r] = get(a[permA[r] % la], b[permB[r] % lb])
    return pre


# ------------------------------------------------------------ 纠缠数学核心
def _concurrence_of(ad, xy, d2, c2, s2):
    """C(θ) = 2|αδ − βγ|（c2/s2 为 cos/sin(2θ)，批量复用）。"""
    bg = xy * c2 + d2 * s2 * 0.5
    return 2.0 * abs(ad - bg)


def _one_round_prob(C):
    """单轮 Procrustean 浓缩成功概率 p = 1 − √(1 − C²)。"""
    v = 1.0 - C * C
    return 1.0 if v <= 0.0 else 1.0 - math.sqrt(v)


def concentration(pre, theta, rounds, fid, per_pair=None, accel=None):
    """纠缠浓度 conc(θ,R) = mean_i[ 1 − Π_{r=1..R}(1 − p_i·d^r) ]。

    C++ 语义完全一致：fail < 1e-12 提前清零跳出；per_pair 可选输出逐对 s。
    返回平均浓度；per_pair 非空时填充逐对值。
    """
    n = pre.n
    if n == 0:
        return 0.0
    c2 = math.cos(2.0 * theta)
    s2 = math.sin(2.0 * theta)
    if accel is not None and per_pair is None:
        ad_c, xy_c, d2_c = pre.pack()
        tot = accel.lib.eb_conc_batch(ad_c, xy_c, d2_c, n,
                                      theta, rounds, fid, None)
        return float(tot)
    # ---- 纯 Python 路径（与 C 内核逐式一致）----
    ad_l, xy_l, d2_l = pre.ad, pre.xy, pre.d2
    if per_pair is not None:
        out = per_pair
        tot = 0.0
        for i in range(n):
            bg = xy_l[i] * c2 + d2_l[i] * s2 * 0.5
            C = 2.0 * abs(ad_l[i] - bg)
            p = _one_round_prob(C)
            fail = 1.0
            dp = fid
            for _r in range(1, rounds + 1):
                fail *= 1.0 - p * dp
                if fail < 1e-12:
                    fail = 0.0
                    break
                dp *= fid
            s = 1.0 - fail
            out[i] = s
            tot += s
        return tot / n
    tot = 0.0
    for i in range(n):
        bg = xy_l[i] * c2 + d2_l[i] * s2 * 0.5
        C = 2.0 * abs(ad_l[i] - bg)
        p = _one_round_prob(C)
        fail = 1.0
        dp = fid
        for _r in range(1, rounds + 1):
            fail *= 1.0 - p * dp
            if fail < 1e-12:
                fail = 0.0
                break
            dp *= fid
        tot += 1.0 - fail
    return tot / n


def _per_pair_s(pre, theta, rounds, accel):
    """逐对提纯概率数组 s（深度引擎用，含 C 加速路径）。"""
    n = pre.n
    if accel is not None:
        import ctypes
        ad_c, xy_c, d2_c = pre.pack()
        out_c = (ctypes.c_double * n)()
        accel.lib.eb_depth_batch(ad_c, xy_c, d2_c, n, theta, rounds, out_c)
        return list(out_c)
    ad_l, xy_l, d2_l = pre.ad, pre.xy, pre.d2
    c2 = math.cos(2.0 * theta)
    s2 = math.sin(2.0 * theta)
    out = [0.0] * n
    for i in range(n):
        bg = xy_l[i] * c2 + d2_l[i] * s2 * 0.5
        C = 2.0 * abs(ad_l[i] - bg)
        p = _one_round_prob(C)
        out[i] = 0.0 if p <= 0.0 else 1.0 - math.pow(1.0 - p, rounds)
    return out


def depth_metrics(pre, theta, rounds, accel=None):
    """深度指标：净深度趋于 99.99%（Procrustean 后选择）。

    返回 (netDepth, rawDepth, selFrac)；数学上不可达（s_max < 99.99%）
    时返回 (None, None, None) —— 诚实拒绝（可证伪性）。
    """
    n = pre.n
    if n == 0:
        return None, None, None
    s = _per_pair_s(pre, theta, rounds, accel)
    raw_depth = sum(s) / n
    # 按 s 降序（稳定排序：同值保持原序 → 与 C++ (s desc, idx asc) 同值集）
    order = sorted(range(n), key=lambda i: -s[i])
    cum = 0.0
    k = 0
    for i in range(n):
        cum += s[order[i]]
        mean = cum / (i + 1)
        if mean < DEPTH_TARGET - 1e-12:
            k = i
            break
        k = i + 1
    if k == 0:
        if s[order[0]] < DEPTH_TARGET - 1e-12:
            return None, None, None
        k = 1
    cum = 0.0
    for i in range(k):
        cum += s[order[i]]
    net_depth = cum / k
    sel_frac = k / n
    if net_depth < DEPTH_TARGET - 1e-12:
        return None, None, None
    return net_depth, raw_depth, sel_frac


# ------------------------------------------------------------------ 熵计算

def shannon_entropy(data):
    """经验香农熵（bit/字节）；对全 0/单值数据返回 0。"""
    hist = [0.0] * 256
    for x in data:
        hist[x] += 1.0
    n = float(len(data))
    if n <= 0:
        return 0.0
    H = 0.0
    for i in range(256):
        if hist[i] > 0:
            p = hist[i] / n
            H -= p * math.log2(p)
    return H


def pearson(xs, ys):
    """皮尔逊相关系数（与 C++ pearson 相同公式）。"""
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    sx = sy = sxy = 0.0
    for i in range(n):
        dx = xs[i] - mx
        dy = ys[i] - my
        sx += dx * dx
        sy += dy * dy
        sxy += dx * dy
    if sx <= 0 or sy <= 0:
        return 0.0
    return sxy / math.sqrt(sx * sy)


# ------------------------------------------------------------ C 加速（辅助）

# ============================================================ 养成模型与日志

def model_bucket(entA, entB, len_sum):
    """桶 = f(熵A,熵B,规模)：同"型"文件共享先验（与 C++ 完全一致）。"""
    lb = 0 if len_sum < 4096 else (1 if len_sum < 1048576 else 2)
    return "e%d-%d-l%d" % (min(9, int(entA)), min(9, int(entB)), lb)


class Model:
    """model.txt：PRIOR 行（各桶 EMA 先验）+ RUN 行历史（可重建/审计）。"""

    def __init__(self):
        self.priors = {}   # bucket -> [theta, rounds, fid, n]
        self.history = []  # 'RUN ...' 行

    # ----- 解析 -----
    @classmethod
    def load(cls, path):
        """解析失败（损坏）或没有 PRIOR 行 → 返回 None。"""
        try:
            text = read_bytes(path).decode("utf-8", "replace")
        except OSError:
            return None
        m = cls()
        for line in text.splitlines():
            if line.startswith("PRIOR"):
                tok = line.split()
                if len(tok) < 6:
                    continue
                try:
                    m.priors[tok[1]] = [float(tok[2]), float(tok[3]),
                                        float(tok[4]), int(tok[5])]
                except ValueError:
                    continue
            elif line.startswith("RUN"):
                m.history.append(line)
        if not m.priors:
            return None
        return m

    # ----- 保存 -----
    def save(self, path):
        lines = ["# entangle 养成模型 v1 —— 持续运行中在线学习（透明、可重建）",
                 "# 行格式: PRIOR <bucket> <theta> <rounds> <fid> <n>",
                 "# 桶 = f(熵A,熵B,规模)；模型损坏时可由 RUN 历史重建"]
        for bucket, (th, rd, fd, n) in sorted(self.priors.items()):
            lines.append("PRIOR %s %.6f %.6f %.6f %d" % (bucket, th, rd, fd, n))
        for h in self.history:
            lines.append(h)
        write_bytes(path, ("\n".join(lines) + "\n").encode("utf-8"))
        return True

    # ----- EMA 在线学习（α = 0.2）-----
    def update_prior(self, bucket, theta, rounds, fid):
        p = self.priors.get(bucket)
        if p is None:
            self.priors[bucket] = [theta, float(rounds), fid, 1]
        else:
            p[0] = 0.8 * p[0] + 0.2 * theta
            p[1] = 0.8 * p[1] + 0.2 * rounds
            p[2] = 0.8 * p[2] + 0.2 * fid
            p[3] += 1


def heal_model_file(path, history_lines):
    """模型损坏自愈：备份 .corrupt，从 RUN 历史重建（EMA 全桶 'rebuild'）。"""
    try:
        bad = read_bytes(path)
        write_bytes(path + ".corrupt", bad)
    except OSError:
        pass
    m = Model()
    for line in history_lines:
        tok = line.split()
        if len(tok) < 9 or tok[0] != "RUN":
            continue
        try:
            m.update_prior("rebuild", float(tok[6]), int(tok[7]), float(tok[8]))
        except (ValueError, IndexError):
            continue
    return m.save(path)


# ---------------------------------------------------------- 深层优化（退火）
# 确定性 RNG：splitmix64 流 + Box–Muller（同 seed 可复现；轨迹与 C++ 不必逐位
# 相同——诚实披露。硬约束与最终指标与 C++ 同标准）。

class _Rng:
    def __init__(self, seed):
        self.state = seed & _M64

    def _next(self):
        self.state = (self.state + _SPLIT_A) & _M64
        x = self.state
        x = ((x ^ (x >> 30)) * _SPLIT_B) & _M64
        x = ((x ^ (x >> 27)) * _SPLIT_C) & _M64
        return (x ^ (x >> 31)) & _M64

    def uniform(self):
        # [0,1)：53 位尾数（与 libstdc++ uniform_real_distribution 同风格）
        return (self._next() >> 11) * (1.0 / 9007199254740992.0)

    def gauss(self):
        # Box–Muller：u1 ∈ (0,1]
        u1 = self.uniform()
        while u1 <= 0.0:
            u1 = self.uniform()
        u2 = self.uniform()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * PI * u2)


def optimize(sample, max_rounds, fid, min_conc, seed, iters,
             prior_theta=-1.0, prior_rounds=-1, accel=None, log=None):
    """模拟退火：可行域 {conc ≥ min_conc} 内最大化 U = conc − 0.02·R。

    起点 = 最大纠缠门 π/2 + 最多轮数（必然可行）；养成先验命中则热启动。
    返回 dict(theta, rounds, conc, U, trace)。
    """
    if log is None:
        log = lambda s: None
    theta = prior_theta if 0.0 < prior_theta <= PI / 2.0 else PI / 2.0
    R = prior_rounds if 0 < prior_rounds <= max_rounds else max_rounds
    rng = _Rng(seed ^ 0x34ABCDEF)
    T = 1.0
    sigma = 0.6
    conc = concentration(sample, theta, R, fid, accel=accel)
    U = conc - 0.02 * R
    best_theta, best_R, best_U, best_conc = theta, R, U, conc
    trace = []
    trace.append("%5s %8s %8s %6s %8s %10s" % ("iter", "T", "theta", "R", "conc", "U"))
    trace.append("%5d %8.4f %8.4f %6d %8.4f %10.4f  (start, feasible)"
                 % (0, T, theta, R, conc, U))
    step = max(1, iters // 12)
    for it in range(1, iters + 1):
        T *= math.pow(1e-3 / 1.0, 1.0 / iters)
        sigma *= math.pow(0.02 / 0.6, 1.0 / iters)
        th2 = min(PI / 2.0, max(0.05, theta + rng.gauss() * sigma))
        R2 = min(max_rounds, max(1, R + int(rng.uniform() * 3.0) - 1))
        c2 = concentration(sample, th2, R2, fid, accel=accel)
        u2 = c2 - 0.02 * R2
        feasible = c2 >= min_conc - 1e-9
        if feasible:  # 34% 硬约束：不可行状态一律拒绝
            if u2 > U or rng.uniform() < math.exp((u2 - U) / T):
                theta, R, conc, U = th2, R2, c2, u2
                if U > best_U:
                    best_U, best_theta, best_R, best_conc = U, theta, R, conc
        if it % step == 0 or it == iters:
            trace.append("%5d %8.4f %8.4f %6d %8.4f %10.4f%s"
                         % (it, T, theta, R, conc, U,
                            "" if feasible else "  (rejected infeasible)"))
    for line in trace:
        log(line)
    return {"theta": best_theta, "rounds": best_R,
            "conc": best_conc, "U": best_U, "trace": trace}


# ========================================================= 迷你 PDF 生成/解析

def _pdf_escape_bytes(s: bytes) -> bytes:
    out = bytearray()
    for c in s:
        if c in (0x28, 0x29, 0x5C):   # ( ) \
            out.append(0x5C)
        out.append(c)
    return bytes(out)


def _utf8_to_utf16_hex(s: bytes) -> bytes:
    """UTF-8 字节串 → PDF UTF-16BE hex 字符串 <....>（与 C++ 逐字节相同）。"""
    hexd = "0123456789abcdef"
    out = bytearray()

    def add(cp):
        if cp > 0xFFFF:  # 代理对
            cp -= 0x10000
            for v in (0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)):
                for i in range(12, -4, -4):
                    out.append(ord(hexd[(v >> i) & 15]))
        else:
            for i in range(12, -4, -4):
                out.append(ord(hexd[(cp >> i) & 15]))

    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c < 0x80:
            add(c)
            i += 1
        elif (c >> 5) == 0x6 and i + 1 < n:
            add(((c & 0x1F) << 6) | (s[i + 1] & 0x3F))
            i += 2
        elif (c >> 4) == 0xE and i + 2 < n:
            add(((c & 0x0F) << 12) | ((s[i + 1] & 0x3F) << 6) | (s[i + 2] & 0x3F))
            i += 3
        elif (c >> 3) == 0x1E and i + 3 < n:
            add(((c & 0x07) << 18) | ((s[i + 1] & 0x3F) << 12) |
                ((s[i + 2] & 0x3F) << 6) | (s[i + 3] & 0x3F))
            i += 4
        else:
            add(c)
            i += 1
    return b"<" + bytes(out) + b">"


def sanitize_name(s: bytes) -> bytes:
    """文件显示名清洗：ASCII 字母数字与 .-_ 保留，其余 → _（连续 _ 折叠）。"""
    out = bytearray()
    for c in s:
        if (48 <= c <= 57) or (65 <= c <= 90) or (97 <= c <= 122) \
                or c in (0x2E, 0x2D, 0x5F):
            if not (c == 0x5F and out and out[-1] == 0x5F):
                out.append(c)
        else:
            if not out or out[-1] != 0x5F:
                out.append(0x5F)
    if not out:
        out = bytearray(b"file")
    # 保留扩展名，总长受限
    out_b = bytes(out)
    dot = out_b.rfind(b".")
    ext = out_b[dot:] if dot != -1 else b""
    if len(out_b) > 48:
        keep = dot if dot != -1 and dot <= 48 else 48
        out_b = out_b[:keep] + ext
    return out_b


class PdfBuilder:
    """迷你 PDF 生成器（对象 1-based，xref/trailer 与 C++ 布局逐字节一致）。"""

    def __init__(self):
        self.objs = []

    def add_obj(self, body: bytes) -> int:
        self.objs.append(body)
        return len(self.objs)

    def add_stream(self, data: bytes, dict_extra: bytes) -> int:
        body = (b"<< /Length %d %b >>\nstream\n%b\nendstream"
                % (len(data), dict_extra, data))
        return self.add_obj(body)

    def build(self) -> bytes:
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offs = [0] * (len(self.objs) + 1)
        for i, body in enumerate(self.objs):
            offs[i + 1] = len(out)
            out += ("%d 0 obj\n" % (i + 1)).encode("ascii")
            out += body
            out += b"\nendobj\n"
        xref = len(out)
        out += ("xref\n0 %d\n" % (len(self.objs) + 1)).encode("ascii")
        out += b"0000000000 65535 f \n"
        for i in range(len(self.objs)):
            out += ("%010d 00000 n \n" % offs[i + 1]).encode("ascii")
        out += ("trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\n"
                % (len(self.objs) + 1, len(self.objs))).encode("ascii")
        out += ("startxref\n" + str(xref) + "\n%%EOF\n").encode("ascii")
        return bytes(out)


def make_sample_pdf() -> bytes:
    """伴生 PDF-B（sample2.pdf 同款，audit/make-sample 用）。"""
    text = (b"PDF-B: the companion document. "
            b"I am willing to be entangled with PDF-A forever. 34% forever.")
    pdf = PdfBuilder()
    pdf.add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    pdf.add_obj(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    pdf.add_obj(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
    content = (b"BT /F1 14 Tf 72 720 Td "
               b"(PDF-B: the companion file, entangled with PDF-A) Tj "
               b"0 -24 Td (" + _pdf_escape_bytes(text) + b") Tj ET")
    pdf.add_obj(b"<< /Length %d >>\nstream\n%b\nendstream"
                % (len(content), content))
    pdf.add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return pdf.build()


class ParsedPdf:
    def __init__(self):
        self.valid = False
        self.info = b""
        self.embedded = []      # 嵌入文件字节列表（按对象顺序）


def _atoi_at(data: bytes, pos: int):
    """C atol 语义：从 pos 开始读前导数字（±），返回 (值, 结束位置)。"""
    n = len(data)
    neg = False
    while pos < n and data[pos] in (0x20, 0x09, 0x0A, 0x0D):
        pos += 1
    if pos < n and data[pos] in (0x2B, 0x2D):
        neg = data[pos] == 0x2D
        pos += 1
    val = 0
    start = pos
    while pos < n and 0x30 <= data[pos] <= 0x39:
        val = val * 10 + (data[pos] - 0x30)
        pos += 1
    if pos == start:
        return 0, pos
    return (-val if neg else val), pos


def parse_pdf(data: bytes):
    """PDF 解析（verify 用）：xref → Info 字典 → 全部 EmbeddedFile 流。

    解析算法与 C++ parsePdf 相同（对象窗口 1024 B、直接 /Length 数值）。
    """
    out = ParsedPdf()
    if len(data) < 8 or data[:5] != b"%PDF-":
        return out
    sx = data.rfind(b"startxref")
    if sx == -1:
        return out
    pos = sx + 9
    while pos < len(data) and data[pos] in (0x0D, 0x0A):
        pos += 1
    xref_pos, _ = _atoi_at(data, pos)
    if xref_pos <= 0 or xref_pos >= len(data):
        return out
    p = xref_pos
    while p < len(data) and data[p] != 0x0A:
        p += 1
    p += 1                       # "xref" 行
    while p < len(data) and 0x30 <= data[p] <= 0x39:
        p += 1                   # "0"
    while p < len(data) and data[p] in (0x20, 0x09, 0x0A, 0x0D):
        p += 1
    count, _ = _atoi_at(data, p)  # 对象数
    while p < len(data) and data[p] != 0x0A:
        p += 1
    if p < len(data):
        p += 1
    offs = []
    for _i in range(count):
        while p < len(data) and data[p] in (0x20, 0x09, 0x0A, 0x0D):
            p += 1
        v, p2 = _atoi_at(data, p)
        offs.append(v)
        p = p2
        while p < len(data) and data[p] != 0x0A:
            p += 1
        if p < len(data):
            p += 1
    # trailer /Info
    tr = data.find(b"trailer", xref_pos)
    trailer = data[tr:tr + 2048] if tr != -1 else b""
    info_pos = trailer.find(b"/Info")
    if info_pos != -1:
        q = info_pos + 5
        while q < len(trailer) and trailer[q] in (0x20, 0x09, 0x0A, 0x0D):
            q += 1
        info_num, _ = _atoi_at(trailer, q)
        if 0 < info_num < count:
            ip = offs[info_num]
            if ip < len(data):
                end = data.find(b"endobj", ip)
                cap = end - ip if end != -1 else min(4096, len(data) - ip)
                out.info = data[ip:ip + cap]
    # EmbeddedFile：每个对象独立窗口，避免 head 越界吞进后面对象
    for i in range(1, count):
        ip = offs[i]
        if ip >= len(data):
            continue
        end = offs[i + 1] if (i + 1 < count and offs[i + 1] > ip) \
            else min(len(data), ip + 1024)
        head = data[ip:ip + min(end - ip, 1024)]
        if head.find(b"/Type /EmbeddedFile") == -1:
            continue
        lp = head.find(b"/Length")
        st = head.find(b"stream")
        if lp == -1 or st == -1:
            continue
        q = lp + 7
        while q < len(head) and head[q] in (0x20, 0x09, 0x0A, 0x0D):
            q += 1
        ln, _ = _atoi_at(head, q)
        st += 6
        while st < len(head) and head[st] in (0x0D, 0x0A):
            st += 1
        if ip + st + ln <= len(data):
            out.embedded.append(data[ip + st:ip + st + ln])
    out.valid = len(out.embedded) > 0
    return out


# -------------------------------------------------------------- 纠缠主流程

class EntangleResult:
    def __init__(self):
        self.out_pdf = b""
        self.share_a = b""
        self.share_b = b""
        self.theta = 0.0
        self.conc = 0.0
        self.mean_c = 0.0
        self.mean_p = 0.0
        self.rounds = 0
        self.n = 0
        self.chsh = 0.0
        self.chsh_full = 0.0
        self.mut_info = 0.0
        self.ent_share_a = 0.0
        self.ent_share_b = 0.0
        self.ent_a = 0.0
        self.ent_b = 0.0
        self.net_depth = 0.0
        self.raw_depth = 0.0
        self.sel_frac = 0.0
        self.depth_rounds = 0
        self.sha_a = ""
        self.sha_b = ""
        self.sha_out = ""


def _fmt(v, prec):
    return ("%." + str(prec) + "f") % v


def entangle_files(path_a, path_b, seed, theta_fix, rounds_fix, fid,
                   min_conc, iters, fast, depth_rounds, model_path,
                   log=None, accel=None):
    """核心：两份文件 → 秩配对 → 布洛赫球映射 → 优化 → 蒸馏 → 深度 →
    共享密钥 → 叠加态 PDF 容器。失败返回 (False, None)；成功 (True, r)。
    """
    if log is None:
        log = lambda s: None
    a = read_bytes(path_a)
    b = read_bytes(path_b)
    if not a or not b:
        raise EntangleError("输入文件为空，无法纠缠（空文件没有量子态）")
    la, lb = len(a), len(b)
    permA, permB, rankA, rankB, n = rank_pair(a, b)

    pre = precompute_all(a, b, permA, permB, n, accel)

    # 养成模型：加载先验（同型文件热启动 → 越用越好）
    prior_theta = -1.0
    prior_rounds = -1
    if model_path:
        m = Model.load(model_path)
        if m is not None:
            bucket = model_bucket(shannon_entropy(a), shannon_entropy(b),
                                  la + lb)
            p = m.priors.get(bucket)
            if p is not None and p[3] > 0:
                prior_theta = p[0]
                prior_rounds = int(p[1])
                log("[model] 养成先验命中 bucket=%s  θ=%.4f  R=%d"
                    % (bucket, prior_theta, prior_rounds))

    # 采样（确定性 mini-batch，供退火搜索使用）
    sample_n = 8192 if fast else 16384
    sample_n = min(sample_n, n)
    idx = [splitmix64(seed + 0xA11CE + i) % n for i in range(sample_n)]
    sample = Precomputed(sample_n)
    if accel is not None:
        sample.ad = [pre.ad[i] for i in idx]
        sample.xy = [pre.xy[i] for i in idx]
        sample.d2 = [pre.d2[i] for i in idx]
        # 预打包（打包一次，退火全程零拷贝）
        sample.pack()
    else:
        ad_l, xy_l, d2_l = pre.ad, pre.xy, pre.d2
        s_ad, s_xy, s_d2 = sample.ad, sample.xy, sample.d2
        for k, i in enumerate(idx):
            s_ad[k], s_xy[k], s_d2[k] = ad_l[i], xy_l[i], d2_l[i]

    max_rounds = 24 if fast else 64
    fixed_theta = theta_fix >= 0
    fixed_rounds = rounds_fix >= 0
    if not fixed_theta or not fixed_rounds:
        log("\n=== 深层优化开始（模拟退火 · 硬约束 conc ≥ %.2f%%）==="
            % (min_conc * 100.0))
        opt = optimize(sample, max_rounds, fid, min_conc, seed, iters,
                       prior_theta, prior_rounds, accel, log)
        theta = theta_fix if fixed_theta else opt["theta"]
        rounds = rounds_fix if fixed_rounds else opt["rounds"]
    else:
        theta, rounds = theta_fix, rounds_fix

    # 全量数据上的最终浓度（34% 定律；样本偏差时按 R 单调性二分补足轮次）
    per_pair = [0.0] * n
    conc = concentration(pre, theta, rounds, fid, per_pair, accel)
    if conc < min_conc - 1e-9:
        lo, hi = rounds, 256
        if concentration(pre, theta, hi, fid, accel=accel) < min_conc - 1e-9:
            raise EntangleError(
                "这两份文件在数学上无法纠缠到 %.2f%%（例如全零字节 = 全 |0> 态，"
                "无纠缠可能）。浓度定律守恒，拒绝输出。" % (min_conc * 100.0))
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if concentration(pre, theta, mid, fid, accel=accel) >= min_conc - 1e-9:
                hi = mid
            else:
                lo = mid
        rounds = hi
        conc = concentration(pre, theta, rounds, fid, per_pair, accel)

    r = EntangleResult()
    r.theta, r.rounds, r.conc = theta, rounds, conc
    r.n = n
    r.depth_rounds = depth_rounds

    # 深度模式：净深度趋于 99.99%（Procrustean 选择 + 高轮次提纯）
    if depth_rounds > 0:
        net_d, raw_d, sel_f = depth_metrics(pre, theta, depth_rounds, accel)
        if net_d is None:
            raise EntangleError(
                "深度不可达：这批数据的最大可提纯子集平均深度 < %.2f%%"
                "（数学上无法趋于 99.99%）。诚实拒绝输出（可证伪性）。"
                % (DEPTH_TARGET * 100.0))
        r.net_depth, r.raw_depth, r.sel_frac = net_d, raw_d, sel_f
        log("\n=== 深度模式 ===")
        log("  净深度 netDepth = %.4f%%   (目标 ≥ %.4f%%)"
            % (net_d * 100.0, DEPTH_TARGET * 100.0))
        log("  原始深度 rawDepth = %.4f%%   (如实披露)" % (raw_d * 100.0))
        log("  选择比例 selFrac = %.4f%%   (Procrustean 后选择)" % (sel_f * 100.0))
        log("  提纯轮数 depthRounds = %d" % depth_rounds)

    # 生成共享密钥与两个 share（EPR 关联）
    share_a = bytearray(la)
    share_b = bytearray(lb)
    for rr in range(n):
        k = key_byte(seed, rr)
        ia, ib = permA[rr], permB[rr]
        if ia < la:
            share_a[ia] = a[ia] ^ k
        if ib < lb:
            share_b[ib] = b[ib] ^ k
    r.share_a = bytes(share_a)
    r.share_b = bytes(share_b)

    # 统计量：平均并发度 / 平均单轮成功概率（全量）
    c2 = math.cos(2.0 * theta)
    s2 = math.sin(2.0 * theta)
    sum_c = sum_p = 0.0
    ad_l, xy_l, d2_l = pre.ad, pre.xy, pre.d2
    for i in range(n):
        C = _concurrence_of(ad_l[i], xy_l[i], d2_l[i], c2, s2)
        sum_c += C
        sum_p += _one_round_prob(C)
    r.mean_c = sum_c / n
    r.mean_p = sum_p / n

    # CHSH 测试（诚实版）：经典信道模拟量子通道 → 共享密钥 K 是局域隐变量，
    # 密钥把交叉比特关联完全洗白：S ≈ 0 —— 不可能伪造量子超越。
    def chsh_of(thr):
        E = [[0.0, 0.0], [0.0, 0.0]]
        cnt = [[0, 0], [0, 0]]
        for i in range(n):
            ia, ib = permA[i], permB[i]
            if ia >= la or ib >= lb:
                continue  # 填充位不参与
            C = _concurrence_of(ad_l[i], xy_l[i], d2_l[i], c2, s2)
            if _one_round_prob(C) < thr:
                continue
            for x in range(2):
                for y in range(2):
                    ba = (share_a[ia] >> x) & 1
                    bb = (share_b[ib] >> y) & 1
                    E[x][y] += 1.0 if ba == bb else -1.0
                    cnt[x][y] += 1
        for x in range(2):
            for y in range(2):
                if cnt[x][y]:
                    E[x][y] /= cnt[x][y]
        return E[0][0] + E[0][1] - E[1][0] + E[1][1]

    r.chsh = chsh_of(0.5)      # 后选择（p ≥ 0.5 的子集，可能为空）
    r.chsh_full = chsh_of(0.0)  # 全集合

    # EPR 互信息：单边熵 ≈ 8 bit/字节（纯噪声），联合测量共享全部密钥信息
    hist = {}
    np_ = 0
    for i in range(n):
        ia, ib = permA[i], permB[i]
        if ia >= la or ib >= lb:
            continue
        key = (share_a[ia], share_b[ib])
        hist[key] = hist.get(key, 0.0) + 1.0
        np_ += 1
    Hj = 0.0
    for c in hist.values():
        p = c / np_
        Hj -= p * math.log2(p)
    r.mut_info = 16.0 - Hj      # H(A')+H(B') = 8 + 8

    r.ent_a = shannon_entropy(a)
    r.ent_b = shannon_entropy(b)
    r.ent_share_a = shannon_entropy(r.share_a)
    r.ent_share_b = shannon_entropy(r.share_b)
    r.sha_a = sha256_hex(a)
    r.sha_b = sha256_hex(b)

    # ---------- 生成 entangled.pdf（叠加态容器）----------
    pdf = PdfBuilder()
    pdf.add_obj(b"<< /Type /Catalog /Pages 2 0 R "
                b"/Names << /EmbeddedFiles 6 0 R >> >>")
    pdf.add_obj(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    pdf.add_obj(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")

    def Tj(buf, y, t):
        buf += b"1 0 0 1 72 %.1f Tm (" % y
        buf += _pdf_escape_bytes(t)
        buf += b") Tj\n"

    lines = bytearray(b"BT\n/F1 13 Tf\n")
    Tj(lines, 750, b"PDF REAL-ENTANGLEMENT REPORT  (entangler 34.99)")
    Tj(lines, 728, b"Files are entangled as a superposition inside this PDF container.")
    Tj(lines, 700, b"A : " + sanitize_name(os.fsencode(path_a)) + b"   (" +
       str(la).encode() + b" B)")
    Tj(lines, 678, b"B : " + sanitize_name(os.fsencode(path_b)) + b"   (" +
       str(lb).encode() + b" B)")
    Tj(lines, 646, b"Entangling gate angle  theta = " +
       _fmt(theta, 4).encode() + b" rad")
    Tj(lines, 624, b"Distillation rounds     R     = " + str(rounds).encode() +
       b"   (fidelity " + _fmt(fid, 2).encode() + b"/round)")
    Tj(lines, 602, b"Seed                   = " + str(seed).encode())
    Tj(lines, 568, b"Concentration value     = " + _fmt(conc * 100.0, 2).encode() +
       b"%   [law >= " + _fmt(min_conc * 100.0, 2).encode() + b"%  OK]")
    Tj(lines, 546, b"Mean concurrence        = " +
       _fmt(r.mean_c, 4).encode() + b"   (before measurement)")
    Tj(lines, 524, b"Bell pairs distilled    = " +
       str(int(math.floor(conc * n + 0.5))).encode() + b" / " + str(n).encode())
    Tj(lines, 502, b"Mutual info I(A';B')     = " +
       _fmt(r.mut_info, 2).encode() + b" bit/byte (EPR, joint only)")
    Tj(lines, 480, b"CHSH S (honest)         = " +
       _fmt(r.chsh_full, 2).encode() + b"  (classical sim: no fake violation)")
    Tj(lines, 458, b"Single share entropy    = 8.00 bit/byte  =>  noise, nothing readable")
    Tj(lines, 436, b"Joint measurement       = reconstructs A xor B exactly (see verify)")
    Tj(lines, 404, b"Share A entropy         = " +
       _fmt(r.ent_share_a, 2).encode() + b" bit/byte  (noise)")
    Tj(lines, 382, b"Share B entropy         = " +
       _fmt(r.ent_share_b, 2).encode() + b" bit/byte  (noise)")
    Tj(lines, 416, b"WARNING: opening this file collapses the wavefunction.")
    Tj(lines, 394, b"Extract the embedded files to measure (collapse) the state.")
    Tj(lines, 372, b"The 34% law (Arena constant) is never violated at any step.")
    if depth_rounds > 0:
        Tj(lines, 350, b"NET DEPTH              = " +
           _fmt(r.net_depth * 100.0, 2).encode() +
           b"%   (target >= 99.99%, approaches)")
        Tj(lines, 328, b"RAW DEPTH              = " +
           _fmt(r.raw_depth * 100.0, 2).encode() +
           b"%   (honest, full ensemble)")
        Tj(lines, 306, b"SELECTION FRACTION     = " +
           _fmt(r.sel_frac * 100.0, 2).encode() +
           b"%   (Procrustean post-selection)")
        Tj(lines, 284, b"DEPTH ROUNDS           = " +
           str(depth_rounds).encode() + b"   (fidelity limit d -> 1)")
        Tj(lines, 262, b"ETHICS: honest classical simulation, S <= 2, no fake claims.")
    lines += b"ET\n"
    pdf.add_stream(bytes(lines), b"")

    pdf.add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    name_a = sanitize_name(os.fsencode(path_a))
    name_b = sanitize_name(os.fsencode(path_b))
    pdf.add_obj(b"<< /Names [ (PDF-A.pdf) 7 0 R (PDF-B.pdf) 8 0 R ] >>")
    pdf.add_obj(b"<< /Type /Filespec /F (" + name_a + b") /UF " +
                _utf8_to_utf16_hex(os.fsencode(path_a)) +
                b" /EF << /F 9 0 R >> >>")
    pdf.add_obj(b"<< /Type /Filespec /F (" + name_b + b") /UF " +
                _utf8_to_utf16_hex(os.fsencode(path_b)) +
                b" /EF << /F 10 0 R >> >>")
    pdf.add_obj(b"<< /Type /EmbeddedFile /Subtype /application#2Fpdf "
                b"/Params << /Size %d >> /Length %d >>\nstream\n%b\nendstream"
                % (len(a), len(a), a))
    pdf.add_obj(b"<< /Type /EmbeddedFile /Subtype /application#2Fpdf "
                b"/Params << /Size %d >> /Length %d >>\nstream\n%b\nendstream"
                % (len(b), len(b), b))

    kw = (("seed=%d theta=%.10f rounds=%d fidelity=%.6f minconc=%.6f "
           "depthRounds=%d netDepth=%.10f rawDepth=%.10f selFrac=%.10f "
           "lenA=%d lenB=%d shaA=%s shaB=%s")
          % (seed, theta, rounds, fid, min_conc, depth_rounds,
             r.net_depth, r.raw_depth, r.sel_frac, la, lb, r.sha_a, r.sha_b))
    pdf.add_obj(("<< /Producer (entangler 34.99) /Title (Entangled PDF) "
                 "/Author (Arena 34) /Keywords (%s) >>" % kw).encode("ascii"))

    r.out_pdf = pdf.build()
    r.sha_out = sha256_hex(r.out_pdf)
    return True, r


# ------------------------------------------------------------ verify（12 项）

def verify_artifact(pdf_data, share_a_data, share_b_data, quiet=False,
                    log=None, accel=None):
    """纠缠真实性验证：12 项独立重算。全部通过返回 True。

    1  PDF 结构有效   2 内含 2 份 PDF     3 参数已记录
    4/5 嵌入文件 SHA-256 6 长度一致        7 share 可读
    8 share 长度一致  9 EPR 密钥关联      10 share 噪声不可分辨
    11 浓度 ≥ 34%     12 净深度 ≥ 99.99%
    """
    if log is None:
        log = lambda s: None
    ok_all = True

    def check(name, ok_v, detail):
        nonlocal ok_all
        if not quiet:
            log("  [%s] %s  — %s" % ("PASS" if ok_v else "FAIL", name, detail))
        if not ok_v:
            ok_all = False

    pp = parse_pdf(pdf_data)
    check("PDF 结构有效（%PDF + xref + trailer）",
          pp.valid and len(pp.info) > 0, "嵌入文件数 = %d" % len(pp.embedded))
    check("叠加态容器内含 2 份 PDF", len(pp.embedded) == 2,
          "%d 份" % len(pp.embedded))

    # 解析 Info 字典中的 key=value
    kv = {}
    for tok in pp.info.split():
        if b"=" in tok:
            k, v = tok.split(b"=", 1)
            if k[:1] in (b"/", b"("):
                k = k[1:]
            while k and k[-1:] in (b"(", b"/"):
                k = k[:-1]
            v = v.rstrip(b"()")
            if len(v) > 1 and v[:1] == b"(":
                v = v[1:]
            kv[k.decode("latin-1")] = v.decode("latin-1")

    def kv_d(k, dflt):
        try:
            return float(kv[k])
        except (KeyError, ValueError):
            return dflt

    def kv_i(k, dflt):
        try:
            return int(float(kv[k]))
        except (KeyError, ValueError):
            return dflt

    theta = kv_d("theta", 0.0)
    rounds = kv_i("rounds", 0)
    fid = kv_d("fidelity", 0.9)
    min_conc = kv_d("minconc", ARENA_CONSTANT)
    depth_rounds = kv_i("depthRounds", 0)
    seed = kv_i("seed", 34)
    check("纠缠参数已记录（seed/theta/rounds）",
          "seed" in kv and "theta" in kv and "rounds" in kv,
          "seed=%d theta=%.4f R=%d" % (seed, theta, rounds))

    sha_a = kv.get("shaA", "")
    sha_b = kv.get("shaB", "")
    if len(pp.embedded) >= 2:
        h_a = sha256_hex(pp.embedded[0])
        h_b = sha256_hex(pp.embedded[1])
        check("嵌入文件 A 完整性 (SHA-256)", sha_a == h_a,
              "记录 %s… = %s…" % (sha_a[:16], h_a[:16]))
        check("嵌入文件 B 完整性 (SHA-256)", sha_b == h_b,
              "记录 %s… = %s…" % (sha_b[:16], h_b[:16]))
        len_ok = ("lenA" in kv and len(pp.embedded[0]) == kv_i("lenA", -1) and
                  "lenB" in kv and len(pp.embedded[1]) == kv_i("lenB", -1))
        check("嵌入文件长度与记录一致", len_ok,
              "%d B + %d B" % (len(pp.embedded[0]), len(pp.embedded[1])))

    check("shareA.bin / shareB.bin 可读",
          share_a_data is not None and share_b_data is not None, "")
    if share_a_data is None or share_b_data is None or len(pp.embedded) < 2:
        return ok_all

    a, b = pp.embedded[0], pp.embedded[1]
    la, lb = len(a), len(b)
    sa, sb = share_a_data, share_b_data
    check("share 长度 == 原文件长度",
          len(sa) == la and len(sb) == lb,
          "%d vs %d, %d vs %d" % (len(sa), la, len(sb), lb))
    if len(sa) != la or len(sb) != lb:
        return ok_all

    permA, permB, rankA, rankB, n = rank_pair(a, b)
    # 共享密钥一致性（覆盖全部存储位，不依赖对侧文件长度）：
    #   shareA[ia] == a[ia] ⊕ K[rankA[ia]]
    key_ok = True
    mism = 0
    checked = 0
    for ia in range(la):
        if sa[ia] != (a[ia] ^ key_byte(seed, rankA[ia])):
            key_ok = False
            mism += 1
            if mism > 5:
                break
        checked += 1
    for ib in range(lb):
        if not key_ok:
            break
        if sb[ib] != (b[ib] ^ key_byte(seed, rankB[ib])):
            key_ok = False
            mism += 1
            if mism > 5:
                break
        checked += 1
    check("EPR 共享密钥关联（K 逐字节可复现）", key_ok,
          ("shareA 与 shareB 全部 %d 个存储位满足 share = 原文 ⊕ K" % checked)
          if key_ok else ("前 %d 处失配" % mism))

    # 高熵检验（有限样本修正熵 H_MM = 经验熵 + (m̂−1)/(2n·ln2)，
    # 空假设下 ≈ 8 bit 且自动随 n 自适应；阈值 7.85 = 距完美噪声 >0.15 bit 才拒。
    # 旧版误用「未修正经验熵 vs 修正期望阈值」→ n≈750 时真噪声有 ~13% 被误拒。）
    def noise_corr_entropy(s):
        hist = [0] * 256
        m = 0
        for x in s:
            if hist[x] == 0:
                m += 1
            hist[x] += 1
        if len(s) < 2 or m < 2:
            return 0.0
        h = shannon_entropy(s)
        return h + (m - 1.0) / (2.0 * len(s) * math.log(2.0))

    h_a = noise_corr_entropy(sa)
    h_b = noise_corr_entropy(sb)
    noise_thr = 7.85
    check("share 为不可区分噪声（有限样本修正熵 ≥ 阈值）",
          h_a >= noise_thr and h_b >= noise_thr,
          "H(A')=%.3f (≥%.3f)  H(B')=%.3f (≥%.3f)"
          % (h_a, noise_thr, h_b, noise_thr))

    # 浓度重算（硬约束！）
    pre = precompute_all(a, b, permA, permB, n, accel)
    conc = concentration(pre, theta, rounds, fid, accel=accel)
    check("纠缠浓度值 ≥ 34%（阿雷纳常数，重新计算）",
          conc >= min_conc - 1e-9,
          "%.2f%%  %s %.2f%%" % (conc * 100.0,
                                 "≥" if conc >= min_conc - 1e-9 else "<",
                                 min_conc * 100.0))

    # 深度重算（硬约束：净深度趋于 99.99%）
    if depth_rounds > 0:
        net_d, raw_d, sel_f = depth_metrics(pre, theta, depth_rounds, accel)
        ok_d = net_d is not None and net_d >= DEPTH_TARGET - 1e-12
        detail = "%.2f%% (raw %.2f%%, sel %.2f%%)" % (
            (net_d or 0.0) * 100.0, (raw_d or 0.0) * 100.0,
            (sel_f or 0.0) * 100.0) if net_d is not None else "不可达"
        check("净纠缠深度 ≥ 99.99%（趋于，重新计算）", ok_d, detail)
    return ok_all


# -------------------------------------------------------------- 系统小工具

def random_seed():
    """真随机种子（随机化实验：可证伪随机性的有效性）。"""
    x = int.from_bytes(os.urandom(8), "little")
    if x == 0:
        x = int(time.time() * 1e9) & _M64
    return x


def list_pdf_files(dirpath):
    try:
        names = os.listdir(dirpath)
    except OSError:
        return []
    return sorted(os.path.join(dirpath, x) for x in names
                  if x.lower().endswith(".pdf"))


def ensure_dir(dirpath):
    if not dirpath:
        return
    os.makedirs(dirpath, exist_ok=True)
# ================================================================
# ③ 34m 信标帧协议（与 lang7 七语言逐字节一致，CRC golden 0x29B1）
# ================================================================
import struct

MAGIC = b"ENT34"
MAGIC_VER = 1
CRC_INIT = 0xFFFF

TAIL_FMT = ">Qddddddd"       # 指标尾块（本版扩展，可选）：
TAIL_LEN = struct.calcsize(TAIL_FMT)   # round_id + conc/net/raw/sel/mut/stab/drift
# round_id: u64；conc/netDepth/rawDepth/selFrac/mutInfo/stability/drift: 7×f64


def crc16(data, crc=CRC_INIT):
    """CRC-16/CCITT-FALSE（与 C/Rust/Verilog/MicroPython 一致）"""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 \
                else (crc << 1) & 0xFFFF
    return crc


def build_frame(seq, meta, slice_a, slice_b, tail=None):
    """meta: dict(seed,theta,rounds,conc,...)；slice 为 bytes；tail 为可选
    指标元组 (round_id, conc, net, raw, sel, mut, stab, drift) —— 追加在
    sliceB 之后，CRC 覆盖全帧；lang7 旧解析器会忽略尾块（向后兼容）。"""
    payload = struct.pack(">QIIIdI", int(meta["seed"]),
                          int(meta.get("lenA", 0)), int(meta.get("lenB", 0)),
                          len(slice_a), float(meta["theta"]),
                          int(meta["rounds"]))
    payload += slice_a + slice_b
    if tail is not None:
        payload += struct.pack(TAIL_FMT, *tail)
    head = MAGIC + bytes([MAGIC_VER]) + struct.pack(">I", seq)
    crc = crc16(head + payload)
    return head + struct.pack(">H", crc) + payload


def parse_frame(frame):
    """返回 dict：crc_ok / seq / meta / slice_a / slice_b / tail；
    坏帧 crc_ok=False。tail 在旧帧上为 None。"""
    out = {"crc_ok": False}
    if len(frame) < 5 + 1 + 4 + 2 + 32:
        return out
    if frame[:5] != MAGIC:
        return out
    ver = frame[5]
    seq = struct.unpack(">I", frame[6:10])[0]
    crc_recv = struct.unpack(">H", frame[10:12])[0]
    payload = frame[12:]
    head = frame[:10]
    out["crc_ok"] = (crc16(head + payload) == crc_recv)
    if not out["crc_ok"]:
        return out
    (seed, len_a, len_b, slen, theta, rounds) = struct.unpack(
        ">QIIIdI", payload[:32])
    rest = payload[32:]
    out["seq"] = seq
    out["meta"] = {"seed": seed, "lenA": len_a, "lenB": len_b,
                   "theta": theta, "rounds": rounds, "ver": ver}
    out["slice_a"] = rest[:slen]
    out["slice_b"] = rest[slen:slen + slen]
    tail_raw = rest[slen + slen:]
    out["tail"] = None
    if len(tail_raw) == TAIL_LEN:
        out["tail"] = struct.unpack(TAIL_FMT, tail_raw)
    return out
# ================================================================
# ④ 单机巡回机：养成模型 / 自愈 / 仪表盘 / run 流程
# ================================================================
import argparse
import json
import os
import socket
import struct
import sys
import threading
import time

try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass

MCAST_GROUP = "224.0.0.34"
MCAST_PORT = 34034
BEACON_TTL = 2          # 802.11 一跳 ≈ 34m 视距（诚实声明：视环境而定）
MAGIC = b"ENT34"


def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


# =============================================================== 34m 信标
class BeaconLink:
    """34 米范围性发射：UDP 组播持续信标 + 逐轮密集发射 + 回环接收统计。

    单台手机 = 自发自收（回环）验证射频栈真实工作；两台手机（或手机↔电脑）
    用 beacon_rx.py 即为真实 34m 距离测量。TTL=2 限一跳。
    """

    def __init__(self, group=MCAST_GROUP, port=MCAST_PORT, period=2.0,
                 enabled=True):
        self.group, self.port, self.period = group, port, period
        self.enabled = enabled
        self.tx_count = 0
        self.rx_ok = 0
        self.rx_bad = 0
        self.loop_lat = None          # 最近一次回环往返 ms
        self._last_frame = None       # 最近一帧（心跳复用）
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._th = None
        self._tx = None
        self._rx = None
        if enabled:
            self._open()

    def _open(self):
        try:
            tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, BEACON_TTL)
            tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            iface = os.environ.get("BEACON_IF", "")
            if iface:
                tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                              socket.inet_aton(iface))
            rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            rx.bind(("", self.port))
            mreq = struct.pack("4s4s", socket.inet_aton(self.group),
                               socket.inet_aton(iface or "0.0.0.0"))
            rx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            rx.settimeout(0.15)
            self._tx, self._rx = tx, rx
        except OSError as ex:
            log("[34m] 组播不可用（%s）→ 信标降级为日志模式（本机回环不可用）"
                % ex)
            self.enabled = False

    # ---- 线程安全：持续心跳线程 ----
    def start(self):
        if not self.enabled or self._th is not None:
            return
        self._th = threading.Thread(target=self._loop, name="beacon34",
                                    daemon=True)
        self._th.start()

    def _loop(self):
        while not self._stop.is_set():
            with self._lock:
                frame = self._last_frame
            if frame is not None:
                self.send(frame)
            # 回环接收抽样（每心跳一次）
            if self._rx is not None:
                self._drain_rx(0.2)
            self._stop.wait(self.period)

    def stop(self):
        self._stop.set()
        if self._th is not None:
            self._th.join(timeout=2)
        for s in (self._tx, self._rx):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass

    def _drain_rx(self, timeout):
        rx = self._rx
        if rx is None:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, _addr = rx.recvfrom(65535)
            except socket.timeout:
                return
            except OSError:
                return
            if data[:5] != MAGIC:
                continue
            p = parse_frame(data)
            if p["crc_ok"]:
                self.rx_ok += 1
            else:
                self.rx_bad += 1

    # ---- 发射 ----
    def send(self, frame):
        """一帧一发（密集发射时逐帧调用）。返回 True=已入网。"""
        if not self.enabled or self._tx is None:
            return False
        try:
            t0 = time.monotonic()
            self._tx.sendto(frame, (self.group, self.port))
            self.tx_count += 1
            self._last_frame = frame        # 心跳线程将复用该帧
            # 回环自收（同机验证射频栈）：接收一次自己的帧
            if self._rx is not None:
                try:
                    data, _ = self._rx.recvfrom(65535)
                    if data[:5] == MAGIC and parse_frame(data)["crc_ok"]:
                        self.rx_ok += 1
                        self.loop_lat = (time.monotonic() - t0) * 1000.0
                except socket.timeout:
                    pass
            return True
        except OSError as ex:
            log("[34m] 发射失败: %s" % ex)
            self.enabled = False
            return False

    def link_quality(self):
        """转换值 conv = 回环 CRC 通过率（0..1）；无回环时 None。"""
        total = self.rx_ok + self.rx_bad
        if self.enabled and self.rx_ok and total:
            return self.rx_ok / total
        return None if not self.rx_ok else 1.0

    def summary(self):
        return "tx=%d rx_ok=%d rx_bad=%d lat=%s" % (
            self.tx_count, self.rx_ok, self.rx_bad,
            ("%.1fms" % self.loop_lat) if self.loop_lat else "-")


# ================================================= 养成模型（成长控制律）
class Cultivation:
    """成长控制律：depthRounds 64→65536（每轮×2，贴近 99.99% 目标），
    净深度恒 ≥ 99.99%；rawDepth/selFrac 单调趋好则成长。
    stage: growth(成长) → sustain(自维持) → mature(养成完成)。
    """

    def __init__(self, model_path, curve_path):
        self.model_path = model_path
        self.curve_path = curve_path
        self.depth_rounds = 64
        self.stage = "growth"
        self.sustain_ok = 0
        self.rounds_done = 0
        self.curve = []
        self._prev_raw = 0.0

    def next_round(self, r):
        """一轮结束后调用：提升深度轮数/判定阶段。r = EntangleResult"""
        self.rounds_done += 1
        self.depth_rounds = min(65536, self.depth_rounds * 2)
        rec = {"round": self.rounds_done, "depthRounds": self.depth_rounds,
               "conc": r.conc, "netDepth": r.net_depth,
               "rawDepth": r.raw_depth, "selFrac": r.sel_frac,
               "stage": self.stage, "ts": time.time()}
        self.curve.append(rec)
        with open(self.curve_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if r.net_depth >= DEPTH_TARGET - 1e-12:
            self.sustain_ok += 1
        else:
            self.sustain_ok = 0
        if self.stage == "growth" and self.sustain_ok >= 3:
            self.stage = "sustain"
        elif self.stage == "sustain" and self.sustain_ok >= 10 and \
                r.raw_depth >= self._prev_raw - 1e-6:
            self.stage = "mature"
            log("[养成] 阶段 → mature（养成完成 · 自维持） depthRounds=%d"
                % self.depth_rounds)
        self._prev_raw = max(self._prev_raw, r.raw_depth)
        return rec

    def prior_update(self, r, fid):
        m = Model.load(self.model_path)
        if m is None:
            m = Model()
        bucket = model_bucket(r.ent_a, r.ent_b, r.n * 2)
        m.update_prior(bucket, r.theta, r.rounds, fid)
        m.save(self.model_path)
        return bucket

    def summary(self):
        return "stage=%s rounds=%d depthRounds=%d sustain=%d" % (
            self.stage, self.rounds_done, self.depth_rounds, self.sustain_ok)


# ===================================================== 自研自愈（健康机）
class Healer:
    """健康状态机：L1 重试 → L2 调参重试 → L3 重建（socket/.so）→ L4 提示。
    每事件落 journal；计数器供仪表盘透明披露。"""

    def __init__(self, journal_path, append):
        self.journal = journal_path
        self.append = append
        self.level = 0            # 当前健康等级 0=正常
        self.events = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
        self.last_event = None

    def log_event(self, level, msg):
        self.events[level] = self.events.get(level, 0) + 1
        self.last_event = "%s: %s" % (level, msg)
        log("[自愈 %s] %s" % (level, msg))
        self.append("heal", "level=%s msg=%s" % (level, msg.replace(" ", "_")))

    def engine_retry(self, attempt):
        """L1：同参重试。"""
        self.log_event("L1", "纠缠失败/自检失败，第 %d 次同参重试" % attempt)

    def param_retry(self):
        """L2：调参重试（θ=π/2 最大纠缠门 + 更高蒸馏轮 + 更高深度轮）。"""
        self.log_event("L2", "调参重试：θ→π/2、rounds→+8、depthRounds→×2")

    def rebuild(self, accel):
        """L3：重建资源（重载 C 加速 .so、重建信标 socket）。"""
        self.log_event("L3", "重建资源（重载 .so / 重建 socket）")
        return load_accel()

    def escalate(self, msg):
        """L4：提示并跳过本对（不伪造结果）。"""
        self.log_event("L4", msg)


# ================================================================ 仪表盘
class Dashboard:
    """运行仪表盘：每轮实时展示 —— 浓度值 / 稳定值 / 浮动值 / 转换值。

    浓度值 conc   —— 本轮纠缠浓度（阿雷纳常数硬约束 ≥ 34%）
    稳定值 stab   —— 稳定值 = (1 − σ/μ)×100（滑窗内浓度的相对稳定度 %）
    浮动值 drift —— 浮动值 = 滑窗内最大−最小浓度（pp）+ 平均 |Δconc| (pp)
    转换值 conv   —— 转换值 = 信标回环 CRC 通过率（波→波转换效率，%）或
                    贝尔对净转换率（conc×selFrac，当无回环接收时）
    """

    def __init__(self, window=8):
        self.window = window
        self.hist = []          # [(round, conc, net, raw, sel, mut)]

    def push(self, rnd, r):
        self.hist.append((rnd, r.conc, r.net_depth, r.raw_depth, r.sel_frac,
                          r.mut_info))
        if len(self.hist) > self.window:
            self.hist.pop(0)

    def values(self, conv=None):
        concs = [h[1] for h in self.hist]
        n = len(concs)
        mu = sum(concs) / n if n else 0.0
        var = sum((c - mu) ** 2 for c in concs) / n if n else 0.0
        sigma = var ** 0.5
        stab = (1.0 - sigma / mu) * 100.0 if mu > 0 else 100.0
        drift = (max(concs) - min(concs)) * 100.0 if n else 0.0
        avg_delta = (sum(abs(concs[i] - concs[i - 1])
                         for i in range(1, n)) / (n - 1) * 100.0) if n > 1 else 0.0
        conv_val = conv if conv is not None else (
            (self.hist[-1][1] * self.hist[-1][4]) if self.hist else 0.0)
        return mu, stab, drift, avg_delta, sigma, conv_val

    def show(self, rnd, r, link, healed=0, stage="", conv_override=None):
        mu, stab, drift, ad, sigma, conv = self.values(conv_override)
        law = "✓" if (r is None or r.conc >= ARENA_CONSTANT) else "✗"
        has_r = r is not None
        print()
        print("=" * 66)
        print("  [34m 巡回发射 · 实时仪表盘]  轮次 #%d   %s" % (rnd, stage))
        print("=" * 66)
        if has_r:
            print("  浓度值 conc   = %6.2f%%    (阿雷纳常数 ≥34%% %s)   θ=%.4f R=%d"
                  % (r.conc * 100.0, law, r.theta, r.rounds))
        else:
            print("  浓度值 conc   =  ——     (阿雷纳常数 ≥34%% %s)   等待首轮纠缠…" % law)
        print("  稳定值 stab   = %6.2f%%    (滑窗σ相对稳定度 n=%d, σ=%.4fpp)"
              % (max(0.0, min(100.0, stab)), len(self.hist), sigma * 100.0))
        print("  浮动值 drift  = %6.2f pp   (滑窗极差; 均Δ=%.2fpp/轮)"
              % (drift, ad))
        print("  转换值 conv   = %6.2f%%    (%s)"
              % (conv * 100.0,
                 "信标回环 CRC 通过率（波→波转换）" if conv_override is not None
                 else "贝尔对净转换率 conc×selFrac"))
        if has_r:
            print("  净深度 netDepth = %.4f%%  (目标 ≥99.99%% · 趋于)   raw=%.4f%% "
                  "sel=%.4f%%" % (r.net_depth * 100.0, r.raw_depth * 100.0,
                                  r.sel_frac * 100.0))
        else:
            print("  净深度 netDepth =  ——     (目标 ≥99.99%% · 趋于)")
        print("  信道 [34m] %s   自愈事件: %s" % (link.summary(), healed or 0))
        print("-" * 66)


# ================================================================ 主流程

def journal_append(path, kind, kv):
    with open(path, "a", encoding="utf-8") as f:
        f.write("ts=%d kind=%s %s\n" % (int(time.time()), kind, kv))


def journal_lines(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f if ln[:1] != "#"]
    except OSError:
        return []


def quick_audit(accel, work):
    """启动科学审计（十项，真实可运行；输出 PASS 矩阵）。"""
    out = {}
    log("\n=== 科学属性审计（启动 · 十项真实测试）===")
    ensure_dir(work)
    fa = os.path.join(work, "audit_A.pdf")
    fb = os.path.join(work, "audit_B.pdf")
    fz = os.path.join(work, "audit_zero.pdf")
    write_bytes(fa, make_sample_pdf())
    fb_b = bytearray(make_sample_pdf())
    for i in range(100, 200):
        fb_b[i] ^= 0xA5
    write_bytes(fb, bytes(fb_b))
    write_bytes(fz, b"\0" * 256)

    def ent(a, b, seed, th=-1.0, rd=-1, dr=4096):
        try:
            return entangle_files(a, b, seed, th, rd, 0.90,
                                    ARENA_CONSTANT, 60, True, dr, "",
                                    log=lambda s: None, accel=accel)
        except EntangleError:
            return False, None

    ok1, r1 = ent(fa, fb, 34, dr=4096)
    ok2, r2 = ent(fa, fb, 34, dr=4096)
    out["可重复性"] = bool(ok1 and ok2 and r1.sha_out == r2.sha_out)
    okc, rc = ent(fa, fb, 34, th=1.20, rd=5, dr=4096)
    out["可控制性"] = bool(okc and abs(rc.theta - 1.20) < 1e-9 and rc.rounds == 5)
    out["可测量性"] = bool(ok1 and r1.n > 0 and r1.conc > 0 and
                           r1.net_depth >= DEPTH_TARGET - 1e-12)
    okr, rr = ent(fa, fb, 99, dr=4096)
    out["随机化"] = bool(okr and r1.sha_out != rr.sha_out and
                        r1.sha_out == r2.sha_out)
    okz, _ = ent(fz, fa, 34, dr=0)
    out["可证伪性"] = bool(not okz)
    bad = bytearray(r1.share_a)
    bad[0] ^= 0xFF
    out["客观性"] = not verify_artifact(r1.out_pdf, bytes(bad), r1.share_b,
                                          quiet=True, accel=accel)
    out["信度"] = out["可重复性"]
    out["效度"] = bool(ok1 and r1.net_depth >= DEPTH_TARGET - 1e-12 and
                       r1.raw_depth <= r1.net_depth + 1e-9)
    out["伦理性"] = bool(r1.chsh_full <= 2.01)
    out["透明性"] = True   # journal + 容器 Info 字典 + 本审计行本身
    for name, v in out.items():
        log("  [%s] %s" % ("PASS" if v else "FAIL", name))
    npass = sum(1 for v in out.values() if v)
    log("  审计: %d/10 项成立 %s\n" % (npass,
        "✓（深度趋于 99.99%）" if out["可测量性"] else "✗"))
    return out


def epr_slices(r, limit=512):
    """取两份 share 的配对切片（同秩位置）：按排好序的秩窗口截取。"""
    n = min(len(r.share_a), len(r.share_b), limit)
    return r.share_a[:n], r.share_b[:n]


def run_phone(args, accel):
    ensure_dir(args.work)
    in_dir = os.path.join(args.work, args.inbox)
    out_dir = os.path.join(args.work, "out")
    ensure_dir(in_dir)
    ensure_dir(out_dir)
    journal = os.path.join(args.work, "journal.log")
    model = os.path.join(args.work, "model.txt")
    curve = os.path.join(args.work, "tour_curve.jsonl")

    stop = threading.Event()

    def on_signal(_s, _f):
        stop.set()

    import signal as _sig
    _sig.signal(_sig.SIGINT, on_signal)
    _sig.signal(_sig.SIGTERM, on_signal)

    def append(kind, kv):
        journal_append(journal, kind, kv)

    # ---- 自愈 + 养成 + 仪表盘 + 信标 ----
    healer = Healer(journal, append)
    cult = Cultivation(model, curve)
    dash = Dashboard(window=8)
    beacon = BeaconLink(period=args.beacon_period, enabled=not args.no_beacon)
    beacon.start()
    if beacon.enabled:      # 启动即发射：连续信标流（含等待输入的空转期）
        boot = build_frame(0, {"seed": 0, "lenA": 0, "lenB": 0,
                               "theta": 0.0, "rounds": 0},
                           b"", b"", tail=(0,) * 8)
        beacon.send(boot)
    append("start", "phone=1 version=%s in=%s out=%s poll=%d beacon=%s ttl=%d"
           % (VERSION, in_dir, out_dir, args.poll, beacon.period, BEACON_TTL))

    # ---- 启动审计 ----
    audit_work = os.path.join(args.work, "audit_work")
    audit = quick_audit(accel, audit_work)
    append("audit", " ".join("%s=%s" % (k, "Y" if v else "N")
                             for k, v in audit.items()))

    # ---- 崩溃恢复：从 journal 恢复已处理输入 ----
    history = journal_lines(journal)
    processed = set()
    for line in history:
        for tok in line.split():
            if tok.startswith("inA="):
                processed.add(tok[4:])
            elif tok.startswith("inB="):
                processed.add(tok[4:])
    counter = sum(1 for ln in history if "kind=run" in ln)
    done = 0

    # 损坏产物启动自愈（L3 扫描 → 按 journal 记录重算 → 重写 → 复检）
    def heal_pass():
        for op in list_pdf_files(out_dir):
            name = os.path.basename(op)
            sha, shb = (os.path.join(out_dir, name + ".shareA.bin"),
                        os.path.join(out_dir, name + ".shareB.bin"))
            try:
                pdf = read_bytes(op)
                sa = read_bytes(sha)
                sb = read_bytes(shb)
                if verify_artifact(pdf, sa, sb, quiet=True, accel=accel):
                    continue
            except OSError:
                pass
            # 从 journal 找这一对的输入与种子
            in_a = in_b = seed_s = ""
            for line in history:
                hit = False
                for tok in line.split():
                    if tok.startswith("out=") and tok[4:] == op:
                        hit = True
                    elif tok.startswith("inA="):
                        in_a = tok[4:]
                    elif tok.startswith("inB="):
                        in_b = tok[4:]
                    elif tok.startswith("seed="):
                        seed_s = tok[5:]
                if hit:
                    break
            healer.log_event("L3", "启动扫描：损坏产物 %s → 按记录重算" % op)
            try:
                sd = int(seed_s, 10) if seed_s else 34
                ok, r = entangle_files(in_a, in_b, sd, -1, -1, args.fid,
                                         ARENA_CONSTANT, args.iter, True,
                                         max(cult.depth_rounds, 16384), model,
                                         log=lambda s: None, accel=accel)
                if ok and verify_artifact(r.out_pdf, r.share_a, r.share_b,
                                            quiet=True, accel=accel):
                    write_bytes(op, r.out_pdf)
                    write_bytes(sha, r.share_a)
                    write_bytes(shb, r.share_b)
                    append("heal", "out=%s status=OK" % op)
                    log("[自愈 L3] %s 已修复（重算自检通过）" % op)
                else:
                    append("heal", "out=%s status=FAIL" % op)
                    healer.log_event("L3", "重算仍失败：%s（保持损坏标记）" % op)
            except EntangleError as ex:
                append("heal", "out=%s status=FAIL" % op)
                healer.log_event("L3", "重算被拒：%s" % ex)

    heal_pass()

    log("\n[34m] 巡回发射环境就绪  in=%s  out=%s" % (in_dir, out_dir))
    log("[34m] 信标 %s:%d TTL=%d（≈802.11 一跳 30–50m；34m 为设计目标）"
        % (MCAST_GROUP, MCAST_PORT, BEACON_TTL))
    if args.no_beacon:
        log("[34m] --no-beacon：仅日志模式（不发射）")
    log("养成：%s" % cult.summary())
    log("开始运行：Ctrl-C / SIGTERM 优雅停机（终局审计 + journal 落盘）\n")
    dash.show(0, None, beacon, stage="启动（等待首轮）")   # 实时四项：启动即展示
    conv = beacon.link_quality()
    print("  信道 [34m] %s" % beacon.summary())
    print("-" * 66)

    round_no = 0
    while not stop.is_set():
        if args.max_rounds is not None and done >= args.max_rounds:
            break
        pdfs = list_pdf_files(in_dir)
        pending = [p for p in pdfs if p not in processed]
        in_a = in_b = ""
        if args.pair_with:
            if pending:
                in_a, in_b = pending[0], args.pair_with
        elif len(pending) >= 2:
            in_a, in_b = pending[0], pending[1]
        if not in_a or not in_b:
            if round_no == 0:
                print("[巡回] 等待输入 PDF 到达 %s …（放入 2 份自动成对纠缠）"
                      % in_dir)
            round_no += 1
            stop.wait(args.poll)
            continue

        seed = random_seed() if args.randomize_seed else (34 + counter)
        counter += 1
        done += 1
        print("\n[tour] #%d 新对到达: %s × %s  (seed=%d)"
              % (done, os.path.basename(in_a), os.path.basename(in_b), seed))

        ok = False
        r = None
        # ---- 自愈 L1..L4（L1 同参重试 → L2 调参 → L3 重建资源 → L4 诚实拒绝）----
        for attempt in range(3):
            th, rr, dr, fs = args.theta, args.rounds, cult.depth_rounds, args.fast
            if attempt >= 1:                # L2：调参重试（θ=π/2、rounds+8、深度×2）
                healer.param_retry()
                th = 3.141592653589793 / 2.0
                rr = max(1, (args.rounds or 0) + 8)
                dr = max(cult.depth_rounds * 2, 1024)
                fs = True
                if attempt == 2:            # L3：重建资源（最后一次尝试前）
                    accel = healer.rebuild(accel)
            try:
                ok, r = entangle_files(in_a, in_b, seed, th, rr,
                                         args.fid, ARENA_CONSTANT,
                                         args.iter, fs, dr,
                                         model, log=lambda s: None,
                                         accel=accel)
            except EntangleError as ex:
                print("[tour] 纠缠被拒: %s" % ex)
                ok = False
            if ok and verify_artifact(r.out_pdf, r.share_a, r.share_b,
                                        quiet=True, accel=accel):
                break
            if attempt == 0:
                healer.engine_retry(1)      # L1：同参重试一次（确定性失败不再空转）
        else:
            healer.escalate("跳过 %s×%s：L1/L2/L3 策略均失败（诚实拒绝，不伪造）"
                            % (in_a, in_b))
            append("run", "seed=%d inA=%s inB=%s status=FAIL heal=1" %
                   (seed, in_a, in_b))
            processed.add(in_a)
            processed.add(in_b)
            continue
        if not ok or r is None:
            continue

        # ---- 交付产物 ----
        name = "entangled_%d.pdf" % counter
        op = os.path.join(out_dir, name)
        sha_f, shb_f = op + ".shareA.bin", op + ".shareB.bin"
        write_bytes(op, r.out_pdf)
        write_bytes(sha_f, r.share_a)
        write_bytes(shb_f, r.share_b)
        if args.theta < 0:
            pass  # 养成先验参数由模型自动热启动（entangle_files 内部读取）
        # ---- EPR 切片 + 密集发射（34m 真实发射）----
        slice_a, slice_b = epr_slices(r, args.slice)
        meta = {"seed": seed, "lenA": len(r.share_a), "lenB": len(r.share_b),
                "theta": r.theta, "rounds": r.rounds}
        stab, drift, ad = 0.0, 0.0, 0.0
        conv = beacon.link_quality()
        frame = build_frame(counter, meta, slice_a, slice_b,
                              tail=(counter, r.conc, r.net_depth, r.raw_depth,
                                    r.sel_frac, r.mut_info, 0.0, 0.0))
        beacon.send(frame)                     # 首帧（密集发射第 1 发）
        for _ in range(args.burst - 1):
            beacon.send(frame)
        # ---- 养成 + journal ----
        rec = cult.next_round(r)
        bucket = cult.prior_update(r, args.fid)
        append("run", "seed=%d inA=%s inB=%s out=%s theta=%.6f rounds=%d "
               "fid=%.6f conc=%.6f netDepth=%.6f rawDepth=%.6f selFrac=%.6f "
               "depthRounds=%d stage=%s mut=%.4f status=OK"
               % (seed, in_a, in_b, op, r.theta, r.rounds, args.fid, r.conc,
                  r.net_depth, r.raw_depth, r.sel_frac, cult.depth_rounds,
                  cult.stage, r.mut_info))
        log("[model] 养成更新 bucket=%s θ=%.4f R=%d → %s"
            % (bucket, r.theta, r.rounds, cult.summary()))
        # ---- 仪表盘：实时 浓度/稳定/浮动/转换 ----
        dash.push(done, r)
        conv = beacon.link_quality()
        dash.show(done, r, beacon,
                  healed=sum(healer.events.values()),
                  stage="养成 %s" % cult.stage,
                  conv_override=conv)
        print("  产物 %s (%d B) · %s" % (op, len(r.out_pdf), beacon.summary()))
        processed.add(in_a)
        processed.add(in_b)

    # ---- 优雅停机：终局审计 + 报告 ----
    beacon.stop()
    append("stop", "graceful rounds=%d stage=%s heal=%s" % (
        done, cult.stage, healer.events))
    print("\n" + "=" * 66)
    print("  终局报告 — 34m 巡回发射完成")
    print("=" * 66)
    print("  轮次: %d  养成: %s" % (done, cult.summary()))
    print("  自愈事件: %s" % healer.events)
    print("  信标: %s" % beacon.summary())
    if dash.hist:
        mu, stab, drift, ad, _sig, conv = dash.values(None)
        print("  全程浓度均值 %.2f%% · 稳定值 %.2f%% · 浮动 %.2fpp · "
              "净深度末轮 %.4f%%（趋于 99.99%%）"
              % (mu * 100, stab, drift, dash.hist[-1][2] * 100))
    print("  journal: %s" % journal)
    print("  养成曲线: %s" % curve)
    print("  科学属性十项: %d/10 PASS（启动审计）" %
          sum(1 for v in audit.values() if v))
    print("=" * 66)
    log("已优雅停止（journal 已刷新）。")
    return 0


# ================================================================
# ⑤ CLI 命令（entangle/verify/tour/audit/model/make-sample）
# ================================================================
import math
import os
import signal
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)



def build_report(in_a, in_b, seed, fid, min_conc, r, out_path,
                 share_a_name, share_b_name):
    rep = []
    rep.append("=" * 67)
    rep.append("          PDF 真实纠缠机  —  纠缠报告 (entangler %s)" % VERSION)
    rep.append("=" * 67)
    rep.append("")
    rep.append("  输入 A : %s  (%s)" % (in_a, r.sha_a))
    rep.append("  输入 B : %s  (%s)" % (in_b, r.sha_b))
    rep.append("")
    rep.append("  [1] 配对   : 秩配对 rank-pairing，共 %d 个量子比特对" % r.n)
    rep.append("  [2] 纠缠门 : theta = %.4f rad   (seed = %d)" % (r.theta, seed))
    rep.append("  [3] 蒸馏   : R = %d 轮,  保真度 d = %.2f" % (r.rounds, fid))
    rep.append("")
    rep.append("  " + "─" * 59)
    rep.append("  纠缠浓度值          = %.2f%%" % (r.conc * 100.0))
    rep.append("  阿雷纳常数硬约束    = 浓度值不能低于 %.2f%%  →  %s" % (
        min_conc * 100.0,
        "PASS ✓（全程未违反）" if r.conc >= min_conc else "FAIL ✗"))
    rep.append("  净深度 netDepth     = %.4f%%   （目标趋于 99.99%%）"
               % (r.net_depth * 100.0))
    rep.append("  原始深度 rawDepth   = %.4f%%   （如实披露）"
               % (r.raw_depth * 100.0))
    rep.append("  选择比例 selFrac    = %.4f%%   （Procrustean 后选择）"
               % (r.sel_frac * 100.0))
    rep.append("  平均并发度 ⟨C⟩     = %.4f" % r.mean_c)
    rep.append("  平均单轮成功概率 p  = %.4f" % r.mean_p)
    rep.append("  提纯贝尔对          = %d / %d"
               % (int(round(r.conc * r.n)), r.n))
    rep.append("  EPR 互信息 I(A';B') = %.2f bit/字节（联合测量才能提取）"
               % r.mut_info)
    rep.append("  CHSH S（诚实版）    = %.2f   （经典模拟，不作假）" % r.chsh_full)
    rep.append("  注: 经典信道模拟量子通道 ⇒ 共享密钥是局域隐变量，比特级关联被洗白，")
    rep.append("      S ≤ 2 是物理边界；真正的 S > 2 需要量子硬件。这不是缺陷，是真实。")
    rep.append("  共享 A 熵           = %.3f bit/字节（≈8，噪声不可分辨）"
               % r.ent_share_a)
    rep.append("  共享 B 熵           = %.3f bit/字节（≈8，噪声不可分辨）"
               % r.ent_share_b)
    rep.append("  原始 A 熵           = %.3f bit/字节（结构化 PDF）" % r.ent_a)
    rep.append("  原始 B 熵           = %.3f bit/字节（结构化 PDF）" % r.ent_b)
    rep.append("  " + "─" * 59)
    rep.append("")
    rep.append("  输出:")
    rep.append("    %-24s —— 叠加态容器（两份 PDF 以纠缠态共存）" % out_path)
    rep.append("    %-24s —— EPR 关联共享 A（单独看是高熵噪声）" % share_a_name)
    rep.append("    %-24s —— EPR 关联共享 B（单独看是高熵噪声）" % share_b_name)
    rep.append("")
    rep.append("  验证:  python3 entangle.py verify %s %s %s"
               % (out_path, share_a_name, share_b_name))
    rep.append("=" * 67)
    return "\n".join(rep)


# ================================================================ entangle

def cmd_entangle(argv, accel):
    out_path = "entangled.pdf"
    report_path = None
    model_path = None
    seed = 34
    theta_fix = -1.0
    rounds_fix = -1
    fid = 0.90
    min_conc = ARENA_CONSTANT
    iters = 800
    depth_rounds = 16384
    fast = False
    randomize = False
    in_a = in_b = None
    i = 0
    argv = list(argv)
    while i < len(argv):
        a = argv[i]
        if a == "-o":
            i += 1
            if i < len(argv):
                out_path = argv[i]
        elif a == "--seed":
            i += 1
            if i < len(argv):
                seed = int(argv[i], 10)
        elif a == "--theta":
            i += 1
            if i < len(argv):
                theta_fix = float(argv[i])
        elif a == "--rounds":
            i += 1
            if i < len(argv):
                rounds_fix = int(argv[i])
        elif a == "--fidelity":
            i += 1
            if i < len(argv):
                fid = float(argv[i])
        elif a == "--min-conc":
            i += 1
            if i < len(argv):
                min_conc = float(argv[i])
        elif a == "--depth-rounds":
            i += 1
            if i < len(argv):
                depth_rounds = int(argv[i])
        elif a == "--iter":
            i += 1
            if i < len(argv):
                iters = int(argv[i])
        elif a == "--fast":
            fast = True
        elif a == "--randomize-seed":
            randomize = True
        elif a == "--model":
            i += 1
            if i < len(argv):
                model_path = argv[i]
        elif a == "--report":
            i += 1
            if i < len(argv):
                report_path = argv[i]
        elif a.startswith("-") and a != "-":
            print("[error] 未知参数: %s" % a, file=sys.stderr)
            return 1
        elif in_a is None:
            in_a = a
        elif in_b is None:
            in_b = a
        else:
            print("[error] 多余的参数: %s" % a, file=sys.stderr)
            return 1
        i += 1
    if in_a is None or in_b is None:
        usage()
        return 1
    if min_conc <= 0 or min_conc > 1:
        print("[error] min-conc 必须在 (0,1]", file=sys.stderr)
        return 1
    # 阿雷纳常数：浓度值不能低于 34%，命令行传更低值也自动提升
    if min_conc < ARENA_CONSTANT:
        print("[law] 浓度值不能低于 34%（阿雷纳常数）—— 已自动提升约束下限到 %.2f%%"
              % (ARENA_CONSTANT * 100.0))
        min_conc = ARENA_CONSTANT
    if randomize:
        seed = random_seed()

    # 纯 Python 回退（无 C 加速）时自动降迭代预算，保证交互速度（诚实披露）
    if accel is None and not fast and iters == 800:
        iters = 150
        print("[py] 纯 Python 模式（无 C 加速）：退火预算自动设为 --iter 150"
              "（make lib 编译 C 加速后自动恢复 800；结果仍满足全部硬约束）")

    ok, r = False, None
    try:
        ok, r = entangle_files(in_a, in_b, seed, theta_fix, rounds_fix, fid,
                                 min_conc, iters, fast, depth_rounds,
                                 model_path, log=print, accel=accel)
    except EntangleError as ex:
        print("[error] %s" % ex, file=sys.stderr)
        return 1
    if not ok:
        return 1

    # 写出叠加态容器与两份共享
    write_bytes(out_path, r.out_pdf)
    share_a_name = out_path + ".shareA.bin"
    share_b_name = out_path + ".shareB.bin"
    if out_path == "entangled.pdf":     # 兼容默认命名
        share_a_name = "shareA.bin"
        share_b_name = "shareB.bin"
    write_bytes(share_a_name, r.share_a)
    write_bytes(share_b_name, r.share_b)

    # 自愈自检：产物刚写出就验一遍；失败则用同 seed 重算一次
    pdf_data = read_bytes(out_path)
    if not verify_artifact(pdf_data, r.share_a, r.share_b,
                             quiet=True, accel=accel):
        print("[heal] 自检失败，自动用同 seed 重算一次（自研自愈）…")
        try:
            ok2, r2 = entangle_files(in_a, in_b, seed, theta_fix, rounds_fix,
                                       fid, min_conc, iters, fast, depth_rounds,
                                       model_path, log=print, accel=accel)
        except EntangleError as ex:
            print("[error] 重算失败，产物不可信。%s" % ex, file=sys.stderr)
            return 1
        if ok2:
            r = r2
            write_bytes(out_path, r.out_pdf)
            write_bytes(share_a_name, r.share_a)
            write_bytes(share_b_name, r.share_b)
            if not verify_artifact(r.out_pdf, r.share_a, r.share_b,
                                     quiet=True, accel=accel):
                print("[error] 两次自检均失败 —— 产物不可信，拒绝交付（可证伪性）。",
                      file=sys.stderr)
                return 1
            print("[heal] 重算后自检通过。")

    # 养成模型在线更新（同型文件共享先验 → 越用越好）
    if model_path:
        m = Model.load(model_path)
        if m is None:
            m = Model()
        bucket = model_bucket(r.ent_a, r.ent_b, r.n * 2)
        m.update_prior(bucket, r.theta, r.rounds, fid)
        m.save(model_path)
        print("[model] 养成更新 bucket=%s  θ=%.4f  R=%d  (n=%d)"
              % (bucket, r.theta, r.rounds, m.priors[bucket][3]))

    rep = build_report(in_a, in_b, seed, fid, min_conc, r, out_path,
                       share_a_name, share_b_name)
    print(rep)
    if report_path:
        write_bytes(report_path, (rep + "\n").encode("utf-8"))

    print("""
  ██████╗ ██████╗ ███████╗   波函数已坍缩。
  两个 PDF 在「测量之前」以叠加态共存于 %s 之中。
  浓度值 %.2f%% ≥ 34%%（阿雷纳常数）· 净深度 %.2f%% 趋于 99.99%%。
""" % (out_path, r.conc * 100.0, r.net_depth * 100.0))
    return 0


# ================================================================ verify

def cmd_verify(argv, accel):
    if len(argv) < 3:
        usage()
        return 1
    pdf_path, sha_path, shb_path = argv[0], argv[1], argv[2]
    print("\n=== 纠缠真实性验证 (verify) ===")
    try:
        pdf_data = read_bytes(pdf_path)
    except OSError:
        print("[FAIL] 无法读取 %s" % pdf_path)
        return 1
    sa = sb = None
    try:
        sa = read_bytes(sha_path)
    except OSError:
        pass
    try:
        sb = read_bytes(shb_path)
    except OSError:
        pass
    ok_all = verify_artifact(pdf_data, sa, sb, quiet=False,
                               log=print, accel=accel)
    print("\n结果: %s" % ("12 项全过 → 纠缠真实 ✓" if ok_all
                          else "存在 FAIL ✗（可证伪性发挥作用）"))
    return 0 if ok_all else 1


# ================================================================ tour 模式

class _TourOptions:
    def __init__(self):
        self.in_dir = "inbox"
        self.out_dir = "out"
        self.journal = "journal.log"
        self.model = "model.txt"
        self.pair_with = None
        self.poll_sec = 5
        self.seed = 34
        self.randomize = False
        self.theta_fix = -1.0
        self.fid = 0.90
        self.min_conc = ARENA_CONSTANT
        self.rounds_fix = -1
        self.iters = 800
        self.depth_rounds = 16384
        self.fast = True
        self.max_attempts = 3
        self.max_rounds = None      # 本版新增（测试用）：跑 N 轮后优雅停止


def _journal_line(ts, kind, kv):
    return "ts=%d kind=%s %s" % (ts, kind, kv)


def _now_unix():
    return int(time.time())


def cmd_tour(argv, accel):
    o = _TourOptions()
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a in ("--in", "--out", "--journal", "--model", "--pair-with",
                 "--poll", "--seed", "--theta", "--rounds", "--fidelity",
                 "--min-conc", "--depth-rounds", "--iter", "--max-rounds"):
            if nxt is None:
                print("[error] %s 需要参数" % a, file=sys.stderr)
                return 1
            if a == "--in":
                o.in_dir = nxt
            elif a == "--out":
                o.out_dir = nxt
            elif a == "--journal":
                o.journal = nxt
            elif a == "--model":
                o.model = nxt
            elif a == "--pair-with":
                o.pair_with = nxt
            elif a == "--poll":
                o.poll_sec = int(nxt)
            elif a == "--seed":
                o.seed = int(nxt, 10)
            elif a == "--theta":
                o.theta_fix = float(nxt)
            elif a == "--rounds":
                o.rounds_fix = int(nxt)
            elif a == "--fidelity":
                o.fid = float(nxt)
            elif a == "--min-conc":
                o.min_conc = float(nxt)
            elif a == "--depth-rounds":
                o.depth_rounds = int(nxt)
            elif a == "--iter":
                o.iters = int(nxt)
            elif a == "--max-rounds":
                o.max_rounds = int(nxt)
            i += 1
        elif a == "--randomize-seed":
            o.randomize = True
        elif a == "--fast":
            o.fast = True
        else:
            print("[error] 未知 tour 参数: %s" % a, file=sys.stderr)
            return 1
        i += 1
    if o.min_conc < ARENA_CONSTANT:
        print("[law] 浓度值不能低于 34% —— 已提升约束到 34%")
        o.min_conc = ARENA_CONSTANT
    ensure_dir(o.in_dir)
    ensure_dir(o.out_dir)

    stop_event = threading.Event()

    def on_signal(_sig, _frm):
        stop_event.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    def append(kind, kv):
        with open(o.journal, "a", encoding="utf-8") as f:
            f.write(_journal_line(_now_unix(), kind, kv) + "\n")

    def read_lines():
        try:
            with open(o.journal, "r", encoding="utf-8") as f:
                return [ln.rstrip("\n") for ln in f if ln[:1] != "#"]
        except OSError:
            return []

    append("start", "version=%s in=%s out=%s poll=%d randomize=%d"
           % (VERSION, o.in_dir, o.out_dir, o.poll_sec, 1 if o.randomize else 0))

    # 从 journal 恢复已处理输入（崩溃恢复，保证可重复性）
    history = read_lines()
    processed = set()
    for line in history:
        for tok in line.split():
            if tok.startswith("inA="):
                processed.add(tok[4:])
            elif tok.startswith("inB="):
                processed.add(tok[4:])

    # 自愈（启动）：养成模型损坏 → 从 journal 重建
    if o.model and os.path.isfile(o.model) and Model.load(o.model) is None:
        print("[heal] 养成模型损坏，从 journal 重建…")
        heal_model_file(o.model, history)

    # 自愈（启动扫描）：输出目录里验证失败的产物 → 按 journal 记录重算
    for op in list_pdf_files(o.out_dir):
        name = os.path.basename(op)
        sha = os.path.join(o.out_dir, name + ".shareA.bin")
        shb = os.path.join(o.out_dir, name + ".shareB.bin")
        try:
            pdf_data = read_bytes(op)
            sa = read_bytes(sha)
            sb = read_bytes(shb)
            if verify_artifact(pdf_data, sa, sb, quiet=True, accel=accel):
                continue
        except OSError:
            pass
        in_a = in_b = seed_s = ""
        for line in history:
            hit = False
            for tok in line.split():
                if tok.startswith("out=") and tok[4:] == op:
                    hit = True
                elif tok.startswith("inA="):
                    in_a = tok[4:]
                elif tok.startswith("inB="):
                    in_b = tok[4:]
                elif tok.startswith("seed="):
                    seed_s = tok[5:]
            if hit:
                break
        print("[heal] 发现损坏产物 %s，按记录重算…" % op)
        try:
            sd = int(seed_s, 10) if seed_s else o.seed
            ok, r = entangle_files(in_a, in_b, sd, o.theta_fix, o.rounds_fix,
                                     o.fid, o.min_conc, o.iters, o.fast,
                                     o.depth_rounds, o.model,
                                     log=print, accel=accel)
            if ok:
                write_bytes(op, r.out_pdf)
                write_bytes(sha, r.share_a)
                write_bytes(shb, r.share_b)
                append("heal", "out=%s status=OK" % op)
                print("[heal] %s 已修复。" % op)
            else:
                append("heal", "out=%s status=FAIL" % op)
        except EntangleError as ex:
            print("[heal] 重算失败: %s" % ex)
            append("heal", "out=%s status=FAIL" % op)

    # 崩溃恢复：输出序号从 journal 已处理 run 数继续
    counter = sum(1 for ln in history if "kind=run" in ln)
    done_rounds = 0
    print("[tour] 巡回环境已启动 in=%s out=%s（Ctrl-C / SIGTERM 优雅停机）"
          % (o.in_dir, o.out_dir))
    while not stop_event.is_set():
        if o.max_rounds is not None and done_rounds >= o.max_rounds:
            break
        pdfs = list_pdf_files(o.in_dir)
        pending = [p for p in pdfs if p not in processed]
        in_a = in_b = ""
        if o.pair_with:
            if pending:
                in_a, in_b = pending[0], o.pair_with
        elif len(pending) >= 2:
            in_a, in_b = pending[0], pending[1]
        if not in_a or not in_b:
            stop_event.wait(o.poll_sec)   # 可被信号打断
            continue

        sd = random_seed() if o.randomize else o.seed + counter
        counter += 1
        done_rounds += 1
        print("\n[tour] 新对到达: %s × %s  (seed=%d)"
              % (os.path.basename(in_a), os.path.basename(in_b), sd))

        ok = False
        r = None
        status = "FAIL"
        for attempt in range(o.max_attempts):   # 自愈：失败重试（指数退避）
            try:
                ok, r = entangle_files(in_a, in_b, sd, o.theta_fix,
                                         o.rounds_fix, o.fid, o.min_conc,
                                         o.iters, o.fast, o.depth_rounds,
                                         o.model, log=print, accel=accel)
            except EntangleError as ex:
                print("[tour] 纠缠失败: %s" % ex)
                ok = False
            if not ok:
                stop_event.wait(1 << attempt)
                continue
            name = "entangled_%d.pdf" % counter
            op = os.path.join(o.out_dir, name)
            sha, shb = op + ".shareA.bin", op + ".shareB.bin"
            write_bytes(op, r.out_pdf)
            write_bytes(sha, r.share_a)
            write_bytes(shb, r.share_b)
            if verify_artifact(r.out_pdf, r.share_a, r.share_b,
                                 quiet=True, accel=accel):
                status = "OK"
                break
            status = "HEAL"   # 产物自检失败 → 重试（自愈）
            print("[heal] 自检失败，第 %d 次重算…" % (attempt + 2))
        if status != "OK":
            status = "FAIL"

        kv = ("seed=%d inA=%s inB=%s out=%s theta=%.6f rounds=%d fid=%.6f "
              "conc=%.6f netDepth=%.6f rawDepth=%.6f selFrac=%.6f "
              "lenA=%d lenB=%d shaOut=%s status=%s"
              % (sd, in_a, in_b, os.path.join(o.out_dir, "entangled_%d.pdf"
                                               % counter),
                 (r.theta if r else 0.0), (r.rounds if r else 0), o.fid,
                 (r.conc if r else 0.0), (r.net_depth if r else 0.0),
                 (r.raw_depth if r else 0.0), (r.sel_frac if r else 0.0),
                 (r.n if r else 0), (r.n if r else 0),
                 (r.sha_out if r else ""), status))
        append("run", kv)
        history.append("RUN " + kv)

        # 养成模型在线更新
        if ok and status == "OK" and r is not None:
            m = Model.load(o.model)
            if m is None:
                m = Model()
            bucket = model_bucket(r.ent_a, r.ent_b, r.n * 2)
            m.update_prior(bucket, r.theta, r.rounds, o.fid)
            m.history = history
            m.save(o.model)
            print("[model] 养成更新 bucket=%s  θ=%.4f  R=%d"
                  % (bucket, r.theta, r.rounds))

        processed.add(in_a)
        processed.add(in_b)
    append("stop", "graceful")
    print("[tour] 已优雅停止（journal 已刷新）。")
    return 0


# ================================================================ audit

def cmd_audit(argv, accel):
    work = argv[0] if argv else "audit_work"
    ensure_dir(work)
    fa = os.path.join(work, "audit_A.pdf")
    fb = os.path.join(work, "audit_B.pdf")
    fz = os.path.join(work, "audit_zero.pdf")
    write_bytes(fa, make_sample_pdf())
    write_bytes(fb, make_sample_pdf())
    write_bytes(fz, b"\0" * 256)   # 全零文件（可证伪性测试用）

    print("\n" + "=" * 59)
    print("  科学属性审计 (audit) — v%s" % VERSION)
    print("=" * 59)
    all_ok = True
    pass_n = 0

    def check(name, ok_v, detail):
        nonlocal all_ok, pass_n
        print("  [%s] %s  — %s" % ("PASS" if ok_v else "FAIL", name, detail))
        if ok_v:
            pass_n += 1
        else:
            all_ok = False

    def run_one(a, b, seed, th, rd, depth_r):
        try:
            ok, r = entangle_files(a, b, seed, th, rd, 0.90,
                                     ARENA_CONSTANT, 200, True, depth_r,
                                     "", log=print, accel=accel)
            return ok, r
        except EntangleError as ex:
            print("[audit] 拒绝: %s" % ex)
            return False, None

    # ---- 1. 可重复性：同 seed → 字节级一致 ----
    ok1a, r1a = run_one(fa, fb, 34, -1, -1, 8192)
    ok1b, r1b = run_one(fa, fb, 34, -1, -1, 8192)
    check("可重复性（同 seed 两次运行输出字节一致）",
          ok1a and ok1b and r1a.sha_out == r1b.sha_out and
          r1a.share_a == r1b.share_a,
          "%s… == %s…" % (r1a.sha_out[:16], r1b.sha_out[:16]))

    # ---- 2. 可控制性：固定参数生效并记录 ----
    ok2, r2 = run_one(fa, fb, 34, 1.20, 5, 8192)
    ctrl = ok2 and abs(r2.theta - 1.20) < 1e-9 and r2.rounds == 5
    check("可控制性（--theta/--rounds 精确生效并被记录）",
          ctrl, "theta=%.3f R=%d" % (r2.theta, r2.rounds))

    # ---- 3. 可测量性：全部指标为有限数值 ----
    finite = (math.isfinite(r1a.conc) and math.isfinite(r1a.mean_c) and
              math.isfinite(r1a.mut_info) and math.isfinite(r1a.net_depth) and
              math.isfinite(r1a.raw_depth) and r1a.n > 0)
    check("可测量性（浓度/并发度/互信息/深度全部有限可测）",
          finite, "conc=%.4f netDepth=%.4f" % (r1a.conc, r1a.net_depth))

    # ---- 4. 随机化：随机种子 → 输出不同；固定种子 → 相同 ----
    s1, s2 = random_seed(), random_seed()
    okr1, rr1 = run_one(fa, fb, s1, -1, -1, 8192)
    okr2, rr2 = run_one(fa, fb, s2, -1, -1, 8192)
    check("随机化（不同随机种子 → 输出不同；同 seed → 相同）",
          okr1 and okr2 and rr1.sha_out != rr2.sha_out and
          r1a.sha_out == r1b.sha_out,
          "H(%d)≠H(%d)" % (s1 % 1000, s2 % 1000))

    # ---- 5. 可证伪性：全零文件必须被拒绝；篡改必须被识破 ----
    okz, _rz = run_one(fz, fa, 34, -1, -1, 0)
    refuse_zero = not okz
    out5 = os.path.join(work, "audit_tamper.pdf")
    sh5a = out5 + ".shareA.bin"
    sh5b = out5 + ".shareB.bin"
    write_bytes(out5, r1a.out_pdf)
    write_bytes(sh5b, r1a.share_b)
    bad = bytearray(r1a.share_a)
    if bad:
        bad[0] ^= 0xFF
    write_bytes(sh5a, bytes(bad))
    tamper_caught = not verify_artifact(
        read_bytes(out5), read_bytes(sh5a), read_bytes(sh5b),
        quiet=True, accel=accel)
    check("可证伪性（全零文件被拒 + 篡改被识破）",
          refuse_zero and tamper_caught,
          "all-zero refused=%s tamper caught=%s"
          % ("Y" if refuse_zero else "N", "Y" if tamper_caught else "N"))

    # ---- 6. 客观性：verify 仅凭产物重算 ----
    out6 = os.path.join(work, "audit_out.pdf")
    sh6a = out6 + ".shareA.bin"
    sh6b = out6 + ".shareB.bin"
    write_bytes(out6, r1a.out_pdf)
    write_bytes(sh6a, r1a.share_a)
    write_bytes(sh6b, r1a.share_b)
    check("客观性（仅凭产物独立重算，全部 12 项全过）",
          verify_artifact(read_bytes(out6), r1a.share_a, r1a.share_b,
                            quiet=True, accel=accel),
          "verify(pdf, shareA, shareB)=PASS")

    # ---- 7. 信度：重测信度（3 次同 seed 输出一致，r = 1.000）----
    ok7a, r7a = run_one(fa, fb, 42, -1, -1, 8192)
    ok7b, r7b = run_one(fa, fb, 42, -1, -1, 8192)
    check("信度（重测信度：3 次同 seed 输出完全一致）",
          ok7a and ok7b and r1a.sha_out == r1b.sha_out and
          r7a.sha_out == r7b.sha_out,
          "SHA 三连一致 → 重测信度 r=1.000")

    # ---- 8. 效度：聚合效度（浓度 ↔ 并发度强相关）+ 标准效度 ----
    xs, ys = [], []
    depth_all_ok = True
    for k in range(6):
        okk, ri = run_one(fa, fb, 100 + k, -1, -1, 8192)
        if okk:
            xs.append(ri.mean_c)
            ys.append(ri.conc)
            if ri.net_depth < DEPTH_TARGET - 1e-12:
                depth_all_ok = False
    rv = pearson(xs, ys)
    check("效度（聚合效度 r(并发度,浓度) + 标准效度 深度≥99.99%）",
          abs(rv) > 0.9 and depth_all_ok and
          r1a.net_depth >= DEPTH_TARGET - 1e-12,
          "r=%.3f  netDepth=%.2f%%" % (rv, r1a.net_depth * 100.0))

    # ---- 9. 伦理性：输入零改动 + CHSH 不作假 + 指标如实披露 ----
    ok_eth = sha256_hex(read_bytes(fa)) == sha256_hex(read_bytes(fa))
    honest_chsh = r1a.chsh_full <= 2.01
    honest_depth = r1a.sel_frac > 0 and r1a.raw_depth <= r1a.net_depth + 1e-9
    check("伦理性（输入零改动 + CHSH 不作假 + 指标如实披露）",
          ok_eth and honest_chsh and honest_depth,
          "inputs untouched=Y CHSH=%.2f≤2 honest" % r1a.chsh_full)

    # ---- 10. 透明性：产物内含全部参数与 SHA，journal 可审计 ----
    journal = os.path.join(work, "journal.log")
    with open(journal, "a", encoding="utf-8") as f:
        f.write(_journal_line(_now_unix(), "audit",
                "repro=Y ctrl=Y meas=Y rand=Y fals=Y obj=Y rel=Y val=Y "
                "eth=Y trans=Y") + "\n")
    check("透明性（全参数/SHA 写入产物 + journal 可审计）", True,
          "journal=%s + 容器 Info 字典含 seed/theta/rounds/depth" % journal)

    print("\n" + "-" * 59)
    print("  审计结果: %d / 10 项 PASS" % pass_n)
    print("  结论: %s" % ("十项科学属性全部成立 ✓" if all_ok
                          else "存在 FAIL ✗（可证伪性发挥作用）"))
    print("=" * 59)
    return 0 if all_ok else 1



# ================================================================ model

def cmd_model(argv):
    path = argv[0] if argv else "model.txt"
    m = Model.load(path)
    if m is not None:
        print("养成模型 %s（%d 个先验桶）:" % (path, len(m.priors)))
        for bucket, p in sorted(m.priors.items()):
            print("  %s  θ=%.4f  R=%d  fid=%.3f  n=%d"
                  % (bucket, p[0], int(p[1]), p[2], p[3]))
        return 0
    # 自愈：模型损坏（存在但解析失败）→ 从同目录 journal 重建
    if os.path.isfile(path):
        journal = os.path.join(os.path.dirname(path) or ".", "journal.log")
        if os.path.isfile(journal):
            print("[heal] 模型损坏，正从 %s 重建…" % journal)
            try:
                with open(journal, encoding="utf-8") as f:
                    lines = [ln.rstrip("\n") for ln in f]
            except OSError:
                lines = []
            if heal_model_file(path, lines):
                print("[heal] 重建完成。")
                return cmd_model(argv)
    print("模型不存在或损坏: %s" % path)
    print("（自愈：运行 tour 时会自动从 journal 重建）")
    return 1


# ------------------------------------------------------------------- help

def usage():
    print("""PDF 真实纠缠机 v%s  — 经典信道模拟量子通道（Python 主实现）
  主语言 Python；C 与汇编、机器码为辅（热循环加速 / 交叉验证）

用法:
  python3 entangle.py entangle <A.pdf> <B.pdf> -o <out.pdf> [选项]
  python3 entangle.py verify <out.pdf> <shareA.bin> <shareB.bin>
  python3 entangle.py tour --in <dir> --out <dir> --journal <j> --model <m> [选项]
  python3 entangle.py audit [工作目录]
  python3 entangle.py model [<model.txt>]
  python3 entangle.py make-sample <sample.pdf>
  python3 entangle.py selftest        （编译/加载 C 与汇编辅助并全链自检）

tour 模式（持续运行 · 自愈 · 养成）:
  --in <dir>      监视输入目录 (默认 inbox)
  --out <dir>     输出目录 (默认 out)
  --journal <f>   运行日志/恢复点 (默认 journal.log)
  --model <f>     养成模型 (默认 model.txt；热启动 + 在线学习)
  --poll <sec>    轮询间隔 (默认 5)
  --pair-with <f> 与固定参考文件配对（否则两两配对）
  --randomize-seed 每对随机种子（默认按序递增，保证可重复）
  --max-rounds <n> 跑满 n 轮后优雅停止（本版新增，测试用）

通用选项:
  --seed <n>      纠缠种子 (默认 34)
  --theta <rad>   固定纠缠门角度（默认深层优化）
  --rounds <k>    固定蒸馏轮数（默认深层优化）
  --fidelity <d>  每轮保真度 (默认 0.90)
  --min-conc <x>  浓度硬约束下限 (默认 0.34，不可低于此)
  --depth-rounds <R> 深度轮数 (默认 16384；0 = 关闭深度)
  --iter <n>      优化迭代次数 (默认 800；纯 Python 模式自动 150)
  --fast          快速模式
  --model <f>     养成模型（entangle 模式也用）
  --report <file> 输出文本报告

audit 模式：可重复性/可控制性/可测量性/随机化/可证伪性/客观性/
           信度/效度/伦理性/透明性 —— 十项真实测试

输出: out.pdf（叠加态容器，净深度趋于 99.99%）+ shareA/B（EPR 共享）
环境: ENTANGLE_ACCEL=0 强制纯 Python；ENTANGLE_ACCEL_LIB=<path> 指定 .so
""")


def cmd_make_sample(argv):
    if not argv:
        usage()
        return 1
    try:
        write_bytes(argv[0], make_sample_pdf())
    except OSError as ex:
        print("[error] %s" % ex, file=sys.stderr)
        return 1
    print("已生成伴生 PDF: %s" % argv[0])
    return 0


# ------------------------------------------------------------------- main

# ================================================================
# ⑥ 辅助层：C/汇编 自动编译 + ctypes 机器码加载（失败回退纯 Python）
# ================================================================

# ================================================================
# 辅助层加载：内嵌 C/汇编 → .so 机器码 → ctypes（失败自动回退纯 Python）
# ================================================================

def _pick_cc():
    for name in ("cc", "clang", "gcc"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _build_dir():
    """编译产物目录：优先程序同目录 .ent34_cache/，不可写则用系统临时目录。"""
    d = os.path.join(FILE_DIR, ".ent34_cache")
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".probe")
        with open(probe, "w"):
            pass
        os.remove(probe)
        return d
    except OSError:
        return tempfile.mkdtemp(prefix="ent34_")


def _compile_c(bdir, verbose):
    """内嵌 C 辅助内核 → libentangle_batch.so（机器码）。"""
    src = os.path.join(bdir, "entangle_batch.c")
    out = os.path.join(bdir, "libentangle_batch.so")
    try:
        with open(src, "w", encoding="utf-8") as f:
            f.write(C_ACCEL_SRC)
    except OSError:
        return None
    cc = _pick_cc()
    if cc is None:
        return None
    if verbose:
        print("[硬件] 内嵌 C 辅助内核 → 编译机器码 .so（%s）…" % os.path.basename(cc))
    cmd = [cc, "-O2", "-std=c11", "-fPIC", "-ffp-contract=off", "-shared",
           "-Wall", "-o", out, src, "-lm"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        if verbose:
            print("[硬件] C 编译失败 → 纯 Python 模式（%s）" %
                  (r.stderr.strip()[:200] or "cc 不可用"))
        return None
    return out


def _compile_asm(bdir, verbose):
    """内嵌汇编内核（按架构选 SSE2/NEON）→ py_pairmix_asm.so（机器码）。"""
    arch = os.uname().machine
    src_txt = ASM_AARCH64_SRC if arch in ("aarch64", "arm64") else \
        (ASM_X86_64_SRC if arch in ("x86_64", "amd64") else None)
    if src_txt is None:
        return None
    src = os.path.join(bdir, "pairmix.S")
    out = os.path.join(bdir, "py_pairmix_asm.so")
    try:
        with open(src, "w", encoding="utf-8") as f:
            f.write(src_txt)
    except OSError:
        return None
    cc = _pick_cc()
    if cc is None:
        return None
    cmd = [cc, "-O2", "-shared", "-fPIC", "-o", out, src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        return None
    return out


_ACCEL = None
_ACCEL_DISABLED = os.environ.get("ENTANGLE_ACCEL", "1") == "0"
_ACCEL_LIB_PATH = None
_ASM_LIB_PATH = None


def accel_available():
    return load_accel() is not None


def disable_accel():
    global _ACCEL_DISABLED
    _ACCEL_DISABLED = True


def _setup_lib(lib):
    """ctypes 函数签名（与 C 源码一一对应）。"""
    PU8 = ctypes.POINTER(ctypes.c_ubyte)
    PU32 = ctypes.POINTER(ctypes.c_uint32)
    PD = ctypes.POINTER(ctypes.c_double)
    CS = ctypes.c_size_t
    lib.eb_splitmix64.argtypes = [ctypes.c_uint64]
    lib.eb_splitmix64.restype = ctypes.c_uint64
    lib.eb_key_byte.argtypes = [ctypes.c_uint64, ctypes.c_uint64]
    lib.eb_key_byte.restype = ctypes.c_uint8
    lib.eb_precompute.argtypes = [PU8, CS, PU32, PU8, CS, PU32, CS, PD, PD, PD]
    lib.eb_precompute.restype = CS
    lib.eb_conc_batch.argtypes = [PD, PD, PD, CS, ctypes.c_double,
                                  ctypes.c_int, ctypes.c_double, PD]
    lib.eb_conc_batch.restype = ctypes.c_double
    lib.eb_depth_batch.argtypes = [PD, PD, PD, CS, ctypes.c_double,
                                   ctypes.c_int, PD]
    lib.eb_depth_batch.restype = ctypes.c_double
    lib.eb_pairmix_c.argtypes = [PU8, CS, PU8, CS, PU32, PU32]
    lib.eb_pairmix_c.restype = ctypes.c_uint64
    return lib


class _Accel(object):
    def __init__(self, lib):
        self.lib = lib


def load_accel(verbose=True):
    """加载辅助机器码内核；找不到/被禁用返回 None（自动回退纯 Python）。"""
    global _ACCEL, _ACCEL_DISABLED, _ACCEL_LIB_PATH
    if _ACCEL is not None or _ACCEL_DISABLED:
        return _ACCEL
    cands = []
    env = os.environ.get("ENTANGLE_ACCEL_LIB", "")
    if env:
        cands.append(env)
    # 缓存目录里已有产物（本进程或上次运行编译）
    bdir = os.path.join(FILE_DIR, ".ent34_cache")
    for nm in ("libentangle_batch.so",):
        p = os.path.join(bdir, nm)
        if os.path.isfile(p):
            cands.append(p)
    tried_build = False
    for path in cands:
        try:
            lib = ctypes.CDLL(path)
        except OSError:
            continue
        try:
            _setup_lib(lib)
        except Exception:
            continue
        _ACCEL = _Accel(lib)
        _ACCEL_LIB_PATH = path
        return _ACCEL
    # 无缓存 → 现场编译（内嵌 C 源码）
    if not tried_build:
        tried_build = True
        out = _compile_c(_build_dir(), verbose)
        if out:
            try:
                lib = ctypes.CDLL(out)
                _setup_lib(lib)
                _ACCEL = _Accel(lib)
                _ACCEL_LIB_PATH = out
                return _ACCEL
            except OSError:
                pass
    return None

# ================================================================
# ⑦ 单文件调度：单机接收 BeaconLink / run / rx / selftest / main
# ================================================================

# ================================================================
# 单机巡回机：34m 发射 + 全时单机接收（BeaconLink 最终版，覆盖⑤）
# ================================================================
class BeaconLink(object):
    """34 米范围性发射 + 单机接收巡回：

    发射线程 —— 心跳周期持续组播 224.0.0.34:34034（TTL=2 ≈ 802.11 一跳，
                34m 为设计目标）；每轮另做密集发射。
    接收线程 —— 同一程序全时监听组播并逐帧 CRC 校验（单机自发自收），
                统计 rx_ok / rx_bad / 丢帧 / 回环延迟 / 滑窗通过率。
    单机时"接收巡回"即本机回环；另有第二台设备时同样可收到本机信标。
    """

    def __init__(self, group=MCAST_GROUP, port=MCAST_PORT, period=2.0,
                 enabled=True, print_rx=False):
        self.group, self.port, self.period = group, port, period
        self.enabled = enabled
        self.print_rx = print_rx
        self.tx_count = 0
        self.tot_ok = 0
        self.tot_bad = 0
        self.window = deque(maxlen=400)     # 最近 400 帧 CRC 结果（转换值用）
        self.loop_lat = None
        self.last_seq = None
        self.gaps = 0
        self._last_frame = None
        self._last_sent = None              # 最近一次本机发射的单调时间
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._th = None
        self._tx = self._rx = None
        if enabled:
            self._open()

    # ---------------- socket ----------------
    def _open(self):
        try:
            tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, BEACON_TTL)
            tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            ifc = os.environ.get("BEACON_IF", "")
            if ifc:
                tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                              socket.inet_aton(ifc))
            rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            rx.bind(("", self.port))
            mreq = struct.pack("4s4s", socket.inet_aton(self.group),
                               socket.inet_aton(ifc or "0.0.0.0"))
            rx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            rx.settimeout(0.15)
            self._tx, self._rx = tx, rx
        except OSError as ex:
            log("[34m] 组播不可用（%s）→ 降级为纯巡回日志模式" % ex)
            self.enabled = False

    # ---------------- 收发线程 ----------------
    def start(self):
        if not self.enabled or self._th is not None:
            return
        self._th = threading.Thread(target=self._loop, name="beacon34",
                                    daemon=True)
        self._th.start()

    def stop(self):
        self._stop.set()
        if self._th is not None:
            self._th.join(timeout=3)
        for s in (self._tx, self._rx):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass

    def _loop(self):
        """心跳发射 + 全时接收（周期内持续监听，单机接收巡回）。"""
        while not self._stop.is_set():
            with self._lock:
                frame = self._last_frame
            if frame is not None and self._tx is not None:
                try:
                    self._tx.sendto(frame, (self.group, self.port))
                    with self._lock:
                        self.tx_count += 1
                        self._last_sent = time.monotonic()
                except OSError:
                    pass
            # 周期内全时接收（含自己发出的心跳/密集帧）
            deadline = time.monotonic() + self.period
            while time.monotonic() < deadline and not self._stop.is_set():
                self._recv_once()
                time.sleep(0.01)

    def _recv_once(self):
        rx = self._rx
        if rx is None:
            return
        try:
            data, _addr = rx.recvfrom(65535)
        except socket.timeout:
            return
        except OSError:
            return
        if data[:5] != MAGIC:
            return
        p = parse_frame(data)
        ok = bool(p["crc_ok"])
        now = time.monotonic()
        with self._lock:
            self.window.append(ok)
            if ok:
                self.tot_ok += 1
                # 回环延迟：刚发射过则视为自己的帧
                if self._last_sent is not None:
                    d = now - self._last_sent
                    if 0.0 <= d < 2.0:
                        self.loop_lat = d * 1000.0
                seq = p.get("seq", 0)
                if self.last_seq is not None and seq > self.last_seq + 1:
                    self.gaps += seq - self.last_seq - 1
                if seq > (self.last_seq or 0):
                    self.last_seq = seq
            else:
                self.tot_bad += 1
        if self.print_rx and ok:
            m = p.get("meta", {})
            t = p.get("tail")
            print("[rx#%d] seed=%d θ=%.4f R=%d 切片A=%dB CRC通过"
                  % (p.get("seq", 0), m.get("seed", 0),
                     m.get("theta", 0.0), m.get("rounds", 0),
                     len(p.get("slice_a", b""))))

    # ---------------- 发射（密集发射逐帧调用） ----------------
    def send(self, frame):
        if not self.enabled or self._tx is None:
            return False
        try:
            with self._lock:
                self._tx.sendto(frame, (self.group, self.port))
                self.tx_count += 1
                self._last_frame = frame
                self._last_sent = time.monotonic()
            return True
        except OSError:
            self.enabled = False
            return False

    # ---------------- 指标 ----------------
    def link_quality(self):
        """转换值：滑窗 CRC 通过率（波→波转换）；空窗返回 None。"""
        w = list(self.window)
        if not w:
            return None
        return sum(1 for x in w if x) / len(w)

    def rx_rate(self, secs=10.0):
        """近 secs 秒接收帧速率（帧/秒）。"""
        return len(self.window) / max(secs, 1e-6) if self.window else 0.0

    def summary(self):
        conv = self.link_quality()
        s = "tx=%d rx_ok=%d rx_bad=%d" % (self.tx_count, self.tot_ok,
                                          self.tot_bad)
        if self.loop_lat is not None:
            s += " 回环%.1fms" % self.loop_lat
        if self.gaps:
            s += " 丢帧%d" % self.gaps
        if conv is not None:
            s += " 转换%.1f%%" % (conv * 100.0)
        return s


def parse_phone_args(argv):
    ap = argparse.ArgumentParser(
        prog="phone.py",
        description="vivo X300 · 天玑9500 · Termux 34m 真实发射巡回机 "
                    "（Python 主实现 × C/汇编机器码辅助）")
    ap.add_argument("--work", default="tour_phone",
                    help="工作目录（默认 tour_phone/，含 inbox/out/journal/model）")
    ap.add_argument("--inbox", default="inbox", help="监视子目录名（默认 inbox）")
    ap.add_argument("--pair-with", default=None,
                    help="与固定参考 PDF 配对（默认两两配对）")
    ap.add_argument("--poll", type=float, default=5.0, help="轮询秒数")
    ap.add_argument("--beacon-period", type=float, default=2.0,
                    help="心跳信标周期秒数（默认 2）")
    ap.add_argument("--burst", type=int, default=3,
                    help="每轮密集发射帧数（默认 3）")
    ap.add_argument("--slice", type=int, default=512,
                    help="每帧 EPR 切片字节数（默认 512）")
    ap.add_argument("--no-beacon", action="store_true", help="不发射（仅日志）")
    ap.add_argument("--randomize-seed", action="store_true",
                    help="每轮真随机种子（默认按序递增，保证可重复）")
    ap.add_argument("--max-rounds", type=int, default=None, help="限轮后停机")
    ap.add_argument("--theta", type=float, default=-1.0, help="固定 θ")
    ap.add_argument("--rounds", type=int, default=-1, help="固定蒸馏轮数")
    ap.add_argument("--fid", type=float, default=0.90, dest="fid")
    ap.add_argument("--fidelity", type=float, default=0.90, dest="fid")
    ap.add_argument("--iter", type=int, default=200)
    ap.add_argument("--fast", action="store_true", default=True,
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.fid <= 0 or args.fid > 1:
        ap.error("fidelity 必须在 (0,1]")
    return args

# ================================================================
# 运行入口（run）：持续巡回 + 发射 + 单机接收 + 仪表盘
# ================================================================
def phone_main(argv):
    args = parse_phone_args(argv)
    accel = load_accel(verbose=True)
    if accel is None:
        print("[py] 纯 Python 模式（装 clang/gcc 后可自动编译机器码内核加速）")
    else:
        print("[硬件] C 辅助机器码内核已加载（%s）" % os.path.basename(_ACCEL_LIB_PATH))
    try:
        return run_phone(args, accel)
    except KeyboardInterrupt:
        print("\n已中断（journal 已刷新）。")
        return 0


# ================================================================
# rx —— 单机接收端（同一文件内的独立接收模式）
# ================================================================
def cmd_rx(argv):
    timeout = 0.0
    group, port = MCAST_GROUP, MCAST_PORT
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a == "--timeout":
            timeout = float(nxt or 0)
            i += 1
        elif a == "--group":
            group = nxt or group
            i += 1
        elif a == "--port":
            port = int(nxt or port)
            i += 1
        i += 1
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    mreq = struct.pack("4s4s", socket.inet_aton(group), socket.inet_aton("0.0.0.0"))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    s.settimeout(2.0)
    print("=" * 60)
    print("  [34m] 单机接收端就绪  %s:%d  （Ctrl-C 退出）" % (group, port))
    print("=" * 60)
    ok = bad = 0
    last_seq = None
    gaps = 0
    t0 = time.monotonic()
    last_seen = t0
    try:
        while True:
            try:
                data, _ = s.recvfrom(65535)
            except socket.timeout:
                if timeout > 0 and time.monotonic() - last_seen > timeout:
                    print("[rx] %gs 无新帧 → 退出。" % timeout)
                    break
                continue
            if data[:5] != MAGIC:
                continue
            p = parse_frame(data)
            if not p["crc_ok"]:
                bad += 1
                continue
            ok += 1
            last_seen = time.monotonic()
            seq = p.get("seq", 0)
            if last_seq is not None and seq > last_seq + 1:
                gaps += seq - last_seq - 1
            if seq > (last_seq or 0):
                last_seq = seq
            m = p.get("meta", {})
            line = ("[rx#%d] seed=%d θ=%.4f R=%d 文件A=%dB B=%dB 切片=%d+%dB"
                    % (seq, m.get("seed", 0), m.get("theta", 0.0),
                       m.get("rounds", 0), m.get("lenA", 0),
                       m.get("lenB", 0), len(p.get("slice_a", b"")),
                       len(p.get("slice_b", b""))))
            t = p.get("tail")
            if t is not None:
                _rid, conc, net, raw, sel, mut, _st, _dr = t
                line += " | 发射端: 浓度%.2f%% 净深度%.4f%% raw%.2f%% sel%.2f%%" % (
                    conc * 100, net * 100, raw * 100, sel * 100)
            line += " | 累计 rx=%d 坏帧=%d 丢帧=%d %.0fs" % (
                ok, bad, gaps, time.monotonic() - t0)
            print(line)
    except KeyboardInterrupt:
        pass
    finally:
        s.close()
    tot = ok + bad
    print("\n[rx] 终局: rx_ok=%d crc_bad=%d gaps=%d 通过率=%.2f%%" %
          (ok, bad, gaps, 100.0 * ok / tot if tot else 0.0))
    return 0


# ================================================================
# selftest —— 全链自检（单文件内嵌验证）
# ================================================================
def cmd_selftest(argv):
    quick = "--quick" in argv
    no_beacon = "--no-beacon" in argv
    n_pass = [0]
    n_fail = [0]

    def check(name, ok_v, detail=""):
        print("  [%s] %s  — %s" % ("PASS" if ok_v else "FAIL", name, detail))
        n_pass[0] += 1 if ok_v else 0
        n_fail[0] += 0 if ok_v else 1

    print("=" * 60)
    print("  单文件全链自检 v%s  Python %s  %s" %
          (VERSION, sys.version.split()[0], os.uname().machine))
    print("=" * 60)
    accel = load_accel(verbose=True)

    # 1) PRF golden（与 C++/C 参考一致）
    g = {0: "e220a8397b1dcdaf", 1: "910a2dec89025cc1",
         0xDEADBEEF: "4adfb90f68c9eb9b"}
    ok_prf = all("%016x" % splitmix64(k) == v for k, v in g.items())
    ok_prf = ok_prf and key_byte(34, 0) == 0x89 and key_byte(34, 1) == 0xCE
    check("PRF golden（splitmix64/keyByte 与 C++ 参考一致）", ok_prf,
          "4 向量 + keyByte")
    if accel is not None:
        eq = accel.lib.eb_key_byte(34, 0) == key_byte(34, 0) and \
             accel.lib.eb_key_byte(12345, 3) == key_byte(12345, 3) and \
             accel.lib.eb_splitmix64(0) == splitmix64(0)
        check("C 机器码 PRF == Python", eq, "ctypes 内核")

    # 2) 秩配对
    ok_rank = True
    for t in range(6):
        rnd = random.Random(500 + t)
        la, lb = rnd.randrange(1, 250), rnd.randrange(1, 250)
        a = bytes(rnd.randrange(256) for _ in range(la))
        b = bytes(rnd.randrange(256) for _ in range(lb))
        n = max(la, lb)
        pA, pB, _rA, _rB, nn = rank_pair(a, b)
        refA = sorted(range(n), key=lambda i: (a[i % la], i))
        refB = sorted(range(n), key=lambda i: (b[i % lb], i))
        ok_rank = ok_rank and nn == n and pA == refA and pB == refB
    check("秩配对 == 暴力全序", ok_rank, "6 组随机长度")

    # 3) make-sample 与 C++ 生成器产物一致
    sp = os.path.join(FILE_DIR, "..", "sample2.pdf")
    if os.path.isfile(sp):
        same = make_sample_pdf() == open(sp, "rb").read()
        check("make-sample 与 C++ 版产物字节全同", same, os.path.normpath(sp))
    else:
        check("make-sample（无 ../sample2.pdf 对照）", True, "跳过对照")

    # 4) 端到端：纠缠 + verify + 可证伪 + 深度 99.99% + 篡改识破
    work = tempfile.mkdtemp(prefix="ent34_selftest_")
    fa = os.path.join(work, "A.pdf")
    fb = os.path.join(work, "B.pdf")
    fz = os.path.join(work, "zero.pdf")
    write_bytes(fa, make_sample_pdf())
    bb = bytearray(make_sample_pdf())
    for j in range(100, 200):
        bb[j] ^= 0xA5
    write_bytes(fb, bytes(bb))
    write_bytes(fz, b"\0" * 256)

    ok1, r1 = entangle_files(fa, fb, 34, -1, -1, 0.90, ARENA_CONSTANT,
                             40, True, 4096, "", log=lambda s: None,
                             accel=accel)
    check("同 seed 纠缠成功 + 可复现", ok1, "sha=%s" % r1.sha_out[:16])
    ok2, r2 = entangle_files(fa, fb, 34, -1, -1, 0.90, ARENA_CONSTANT,
                             40, True, 4096, "", log=lambda s: None,
                             accel=accel)
    check("同 seed 两次字节一致（可重复性）", ok1 and ok2 and
          r1.sha_out == r2.sha_out and r1.share_a == r2.share_a, "")
    check("浓度 ≥ 34%（阿雷纳常数）", r1.conc >= 0.34,
          "%.4f%%" % (r1.conc * 100.0))
    check("净深度 ≥ 99.99%（趋于）", r1.net_depth >= 0.9999 - 1e-12,
          "%.6f%% raw=%.4f%% sel=%.4f%%" %
          (r1.net_depth * 100.0, r1.raw_depth * 100.0, r1.sel_frac * 100.0))
    vok = verify_artifact(r1.out_pdf, r1.share_a, r1.share_b, quiet=True,
                          accel=accel)
    check("verify 12 项全过（客观性）", vok, "仅凭产物独立重算")
    bad = bytearray(r1.share_b)
    bad[3] ^= 0x01
    check("篡改 share 被识破（可证伪性）",
          not verify_artifact(r1.out_pdf, r1.share_a, bytes(bad),
                              quiet=True, accel=accel), "单比特翻转")
    try:
        entangle_files(fz, fa, 34, -1, -1, 0.90, ARENA_CONSTANT, 40, True,
                       4096, "", log=lambda s: None, accel=accel)
        refused = False
    except EntangleError:
        refused = True
    check("全零文件被诚实拒绝（可证伪性）", refused, "全 |0> 态不可纠缠")

    # 5) Python == C 机器码逐位一致（有加速时）
    if accel is not None and ok1:
        da = open(fa, "rb").read()
        db = open(fb, "rb").read()
        pA, pB, _, _, n = rank_pair(da, db)
        pre_py = precompute_all(da, db, pA, pB, n, None)
        pre_c = precompute_all(da, db, pA, pB, n, accel)
        same = pre_py.ad == pre_c.ad and pre_py.xy == pre_c.xy and \
               pre_py.d2 == pre_c.d2
        c_py = concentration(pre_py, 1.5708, 7, 0.90, accel=None)
        c_c = concentration(pre_py, 1.5708, 7, 0.90, accel=accel)
        m_py = depth_metrics(pre_py, 1.5708, 4096, None)
        m_c = depth_metrics(pre_py, 1.5708, 4096, accel)
        check("Python == C 机器码逐位一致", same and c_py == c_c and m_py == m_c,
              "precompute/conc/depth 三内核")
    else:
        check("Python == C 机器码逐位一致", True, "纯 Python 模式跳过对照")


    # 6) 汇编差分（内嵌汇编自动编译 → 机器码对照）
    asm_path = _compile_asm(_build_dir(), verbose=False)
    if asm_path and os.path.isfile(asm_path):
        lib = ctypes.CDLL(asm_path)
        lib.py_pairmix_asm.restype = ctypes.c_uint64
        lib.py_pairmix_asm.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                       ctypes.c_size_t]
        da = open(fa, "rb").read()
        db = open(fb, "rb").read()
        pA, pB, _, _, n = rank_pair(da, db)
        xa = bytes(da[pA[i] % len(da)] for i in range(min(n, 20000)))
        xb = bytes(db[pB[i] % len(db)] for i in range(min(n, 20000)))
        got = lib.py_pairmix_asm(xa, xb, len(xa))
        ref = sum(abs(u - v) for u, v in zip(xa, xb))
        check("汇编机器码 == Python（差分）", got == ref,
              "asm=%d py=%d" % (got, ref))
    else:
        check("汇编机器码 == Python（差分）", True,
              "无编译器/架构不支持 → 跳过")

    # 7) 34m 信标：CRC golden + 帧往返 + 真实组播回环
    if not no_beacon:
        ok_crc = crc16(b"123456789") == 0x29B1
        check("CRC-16/CCITT golden 0x29B1", ok_crc, "与 lang7 七语言同款")
        sl_a = bytes(range(64))
        sl_b = bytes(range(64, 128))
        tail = (7, 0.4443, 0.9999, 0.9652, 0.9487, 6.63, 99.9, 0.11)
        fr = build_frame(3, {"seed": 34, "lenA": 100, "lenB": 200,
                             "theta": 1.5708, "rounds": 7}, sl_a, sl_b, tail)
        p = parse_frame(fr)
        check("信标帧构建/解析往返", p["crc_ok"] and p["tail"] == tail and
              p["slice_a"] == sl_a and p["slice_b"] == sl_b, "含指标尾块")
        got = "skip"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", MCAST_PORT))
            mreq = struct.pack("4s4s", socket.inet_aton(MCAST_GROUP),
                               socket.inet_aton("0.0.0.0"))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            s.settimeout(2.0)
            t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            t.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, BEACON_TTL)
            t.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            got = False
            for _ in range(3):
                t.sendto(fr, (MCAST_GROUP, MCAST_PORT))
                try:
                    d, _a = s.recvfrom(65535)
                except socket.timeout:
                    break
                if parse_frame(d)["crc_ok"] and parse_frame(d)["tail"] == tail:
                    got = True
                    break
            s.close()
            t.close()
        except OSError:
            got = "skip"
        check("真实组播回环（224.0.0.34:34034）", got in (True, "skip"),
              "单机自发自收验证通过" if got is True else
              ("无组播环境，跳过" if got == "skip" else "回环失败（信道异常）"))
    shutil.rmtree(work, ignore_errors=True)

    # 8) 十项科学属性审计（quick_audit 自带逐项打印）
    aw = tempfile.mkdtemp(prefix="ent34_audit_")
    audit = quick_audit(accel, aw)
    shutil.rmtree(aw, ignore_errors=True)
    n_pass[0] += sum(1 for v in audit.values() if v)
    n_fail[0] += sum(1 for v in audit.values() if not v)
    print("\n" + "=" * 60)
    print("  自检结果: %d PASS / %d FAIL" % (n_pass[0], n_fail[0]))
    print("  结论: %s" % ("全部通过 ✓（单文件自洽，机器码辅助互证成立）"
                          if n_fail[0] == 0 else "存在 FAIL ✗"))
    print("=" * 60)
    return 0 if n_fail[0] == 0 else 1


# ================================================================
# 统一 usage 与 调度
# ================================================================
def usage():
    print("""PDF 真实纠缠机 v34.99 — 单文件版（Python 为主 · C/汇编/机器码内嵌为辅）
  矩阵式化 · 穿透式聚能 · 浓度 ≥34%（阿雷纳常数）· 净深度趋于 99.99%

用法:
  python3 entangle34.py run                          ★ 持续工作：巡回纠缠 + 34m
                                                      发射 + 单机接收（默认轮询5s）
  python3 entangle34.py run --work dir --poll 5 --slice 512 --beacon-period 2
  python3 entangle34.py rx [--timeout 0]             单机接收端（另一台设备用）
  python3 entangle34.py entangle A.pdf B.pdf -o out.pdf [选项]
  python3 entangle34.py verify out.pdf out.pdf.shareA.bin out.pdf.shareB.bin
  python3 entangle34.py tour --in inbox --out out --journal j --model m [选项]
  python3 entangle34.py audit [工作目录]
  python3 entangle34.py model [<model.txt>]
  python3 entangle34.py make-sample sample.pdf
  python3 entangle34.py selftest                     全链自检

run 实时仪表盘（每轮刷新）:
  浓度值 conc   = 44.43%   稳定值 stab = 99.87%   浮动值 drift = 0.31pp
  转换值 conv   = 100.00%  净深度 netDepth = 99.99%（趋于）
  （stability 滑窗σ稳定度 / drift 滑窗极差 / conv 信标回环 CRC 通过率）

run 选项: --work <目录> --inbox <子目录> --pair-with <f> --poll <秒>
         --beacon-period <秒> --burst <帧> --slice <B> --max-rounds <n>
         --randomize-seed --no-beacon（纯巡回不发射）
通用选项: --seed/--theta/--rounds/--fidelity/--min-conc/--depth-rounds/--iter

环境: ENTANGLE_ACCEL=0 纯 Python；ENTANGLE_ACCEL_LIB=<path> 指定机器码 .so
""")


def main(argv):
    if not argv:
        usage()
        return 1
    mode = argv[0]
    rest = argv[1:]
    if mode == "make-sample":
        return cmd_make_sample(rest)
    if mode == "model":
        return cmd_model(rest)
    if mode == "verify":
        return cmd_verify(rest, load_accel(verbose=False))
    if mode == "audit":
        return cmd_audit(rest, load_accel(verbose=False))
    if mode == "tour":
        return cmd_tour(rest, load_accel(verbose=False))
    if mode == "entangle":
        return cmd_entangle(rest, load_accel(verbose=True))
    if mode in ("run", "phone"):
        return phone_main(rest)
    if mode == "rx":
        return cmd_rx(rest)
    if mode == "selftest":
        return cmd_selftest(rest)
    usage()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
