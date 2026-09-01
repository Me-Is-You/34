# -*- coding: utf-8 -*-
# ============================================================================
# rust_twin.py — Rust 模块的 Python 直译孪生（沙盒无 cargo 时用于互证）
#
# 与 lang7/rust/src/lib.rs 逐函数对应。真机/CI 上 cargo build 后，
# orchestrator 会优先 ctypes 加载原生 libentangle_rust.so。
# ============================================================================
import math
from bisect import insort

PI = math.pi
ARENA = 0.34
DEPTH_TARGET = 0.9999
PHI = 0x9E3779B97F4A7C15


def splitmix64(x):
    x = (x + PHI) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return (x ^ (x >> 31)) & 0xFFFFFFFFFFFFFFFF


def key_byte(seed, r):
    seed = int(seed)
    x = (seed ^ (r * PHI)) & 0xFFFFFFFFFFFFFFFF
    return (splitmix64(x) >> 56) & 0xFF


def phi(x):
    return PI * x / 510.0


def rank_pair(a, b):
    n = max(len(a), len(b))
    pa = sorted(range(n), key=lambda i: (a[i % len(a)], i))
    pb = sorted(range(n), key=lambda i: (b[i % len(b)], i))
    return pa, pb


def _pair_math(x, y, c2, s2):
    fa, fb = phi(x), phi(y)
    cfa, sfa, cfb, sfb = math.cos(fa), math.sin(fa), math.cos(fb), math.sin(fb)
    xv, yv = cfa * sfb, sfa * cfb
    ad = (cfa * cfb) * (sfa * sfb)
    bg = xv * yv * c2 + (yv * yv - xv * xv) * s2 * 0.5
    return 2.0 * abs(ad - bg)


def concentration(a, b, theta, rounds, fid):
    pa, pb = rank_pair(a, b)
    n = len(pa)
    if n == 0:
        return 0.0
    rounds = int(rounds)
    c2, s2 = math.cos(2 * theta), math.sin(2 * theta)
    tot = 0.0
    for i in range(n):
        x = a[pa[i] % len(a)]
        y = b[pb[i] % len(b)]
        C = _pair_math(x, y, c2, s2)
        v = 1.0 - C * C
        p = 1.0 if v <= 0 else 1.0 - math.sqrt(v)
        fail = 1.0
        dp = fid
        for _ in range(rounds):
            fail *= 1.0 - p * dp
            dp *= fid
            if fail < 1e-12:
                fail = 0.0
                break
        tot += 1.0 - fail
    return tot / n


def depth_metrics(a, b, theta, rounds):
    pa, pb = rank_pair(a, b)
    n = len(pa)
    if n == 0:
        return None
    c2, s2 = math.cos(2 * theta), math.sin(2 * theta)
    s = []
    for i in range(n):
        x = a[pa[i] % len(a)]
        y = b[pb[i] % len(b)]
        C = _pair_math(x, y, c2, s2)
        v = 1.0 - C * C
        p = 1.0 if v <= 0 else 1.0 - math.sqrt(v)
        s.append(0.0 if p <= 0 else 1.0 - (1.0 - p) ** rounds)
    raw = sum(s) / n
    s.sort(reverse=True)
    cum = 0.0
    k = 0
    for i in range(n):
        cum += s[i]
        if cum / (i + 1) < DEPTH_TARGET - 1e-12:
            k = i
            break
        k = i + 1
    if k == 0:
        return None
    net = sum(s[:k]) / k
    if net < DEPTH_TARGET - 1e-12:
        return None
    return net, raw, k / n


def crc16(data, crc=0xFFFF):
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc
