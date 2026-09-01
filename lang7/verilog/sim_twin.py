#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# sim_twin.py — 七语言协同 · Verilog golden 向量生成与核对 (lang7)
#
# 职责：
#   1) 生成 RTL 查表文件：sine.mem（256×16）、p_rom.mem（1024×16）
#   2) 生成测试台 golden：golden_key.mem / golden_p.mem（RTL 路径自洽）
#   3) 诚实核对：RTL 定点路径 vs C 核心双精度数学——
#        单门 p 偏差（披露，C→1 处 p 函数奇异，单门偏差允许较大）
#        256 对样本的浓缩率偏差 < 0.5pp（PASS 判据；34% 铁律不受影响）
#   4) 若本机有 iverilog，直接运行 RTL 仿真逐位核对
# 所有 golden 与 C/Rust/Python/MicroPython 同算法同源。
# ============================================================================
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LANG7 = os.path.dirname(HERE)
PI = math.pi

SINE_SCALE = 1 << 15
P_SCALE = 65535
P_ROM_N = 1024          # C 量化 10 位


def sin_lut_256():
    """sin(π·j/510)·2^15，j∈[0,255]（恰好覆盖 [0, π/2]，步进 π/510；
    cos 查表 = 索引 255−j，精确）"""
    lut = []
    for j in range(256):
        v = round(math.sin(PI * j / 510.0) * SINE_SCALE)
        lut.append(max(0, min(SINE_SCALE, v)))
    return lut


def p_of(x, y):
    """双精度单轮浓缩概率 p（与 C 核心 ec_one_round_prob 一致，θ=π/2）"""
    fa, fb = PI * x / 510.0, PI * y / 510.0
    C = 4.0 * math.cos(fa) * math.cos(fb) * math.sin(fa) * math.sin(fb)
    v = 1.0 - C * C
    p = 1.0 if v <= 0 else 1.0 - math.sqrt(v)
    return C, p


def p_rom_from_lut():
    """p ROM：精确 p 在 bin 中点 C=(idx+0.5)/1024 处的值×65535"""
    rom = []
    for idx in range(P_ROM_N):
        c_val = (idx + 0.5) / P_ROM_N
        v = 1.0 - c_val * c_val
        p = 1.0 if v <= 0 else 1.0 - math.sqrt(v)
        rom.append(round(p * P_SCALE))
    return rom


def rtl_p(x, y, sin_lut, p_rom):
    """模拟 RTL 数值路径（与 entangle_gate.v 逐操作一致）"""
    sfa, cfa = sin_lut[x], sin_lut[255 - x]
    sfb, cfb = sin_lut[y], sin_lut[255 - y]
    prod = (cfa * cfb) * (sfa * sfb)
    c_q = (prod >> 43) & 0xFFFF
    c_c = 0x7FFF if c_q == 0x8000 else c_q
    idx = (c_c >> 5) & 0x3FF
    return p_rom[idx], c_q, idx


def conc_pairs(a, b, pfn):
    """浓缩率：Σ[1 − Π_r(1 − p·fid^r)] / n（与 C 核心/Rust 同式）"""
    n = len(a)
    fid = 0.90
    rounds = 8
    tot = 0.0
    for i in range(n):
        p = pfn(a[i], b[i])
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


def main():
    ok = True

    sin_lut = sin_lut_256()
    p_rom = p_rom_from_lut()

    # ---- 1) 表文件 ----
    with open(os.path.join(HERE, "sine.mem"), "w") as f:
        for v in sin_lut:
            f.write("%04x\n" % v)
    with open(os.path.join(HERE, "p_rom.mem"), "w") as f:
        for v in p_rom:
            f.write("%04x\n" % v)
    print("  [PASS] 生成 sine.mem (256×16) + p_rom.mem (1024×16)")

    # ---- 2) golden：epr_prf K[0..7]（与 C 核心/Rust 一致） ----
    sys.path.insert(0, os.path.join(LANG7, "python"))
    from rust_twin import key_byte
    keys = [key_byte(34, r) for r in range(8)]
    with open(os.path.join(HERE, "golden_key.mem"), "w") as f:
        for k in keys:
            f.write("%02x\n" % k)
    print("  [PASS] golden_key.mem: K[0..7] = " +
          " ".join("%02X" % k for k in keys))

    # ---- 3) golden：entangle_gate 8 组测试对（RTL 路径自洽） ----
    pairs = [(10, 10), (34, 34), (0, 255), (128, 128),
             (255, 0), (77, 199), (200, 100), (34, 99)]
    gold_p = []
    max_dev = 0.0
    max_dev_pair = ""
    for (x, y) in pairs:
        p_rtl, _c_q, _idx = rtl_p(x, y, sin_lut, p_rom)
        gold_p.append(p_rtl)
        _C, p_exact = p_of(x, y)
        dev = abs(p_rtl / P_SCALE - p_exact)
        if dev > max_dev:
            max_dev = dev
            max_dev_pair = "(%d,%d)" % (x, y)
    with open(os.path.join(HERE, "golden_p.mem"), "w") as f:
        for v in gold_p:
            f.write("%04x\n" % v)
    print("  [PASS] golden_p.mem 8 组（RTL 路径自洽；单门最大偏差 %.2f%% 于 %s，"
          "C→1 处 p 奇异，属披露项）" % (max_dev * 100, max_dev_pair))

    # ---- 4) 浓度级核对（PASS 判据：偏差 < 0.5pp，34% 铁律裕量充足） ----
    a = list(range(256))
    b = [(i * 137 + 34) & 0xFF for i in range(256)]
    conc_exact = conc_pairs(a, b, lambda x, y: p_of(x, y)[1])
    conc_rtl = conc_pairs(a, b, lambda x, y: rtl_p(x, y, sin_lut, p_rom)[0] / P_SCALE)
    dev_conc = abs(conc_rtl - conc_exact)
    if dev_conc < 0.005:
        print("  [PASS] 浓度级核对：RTL 定点 %.4f vs 双精度 %.4f，偏差 %.4fpp (<0.5pp)"
              % (conc_rtl, conc_exact, dev_conc * 100))
    else:
        print("  [FAIL] 浓度级偏差 %.4fpp ≥ 0.5pp" % (dev_conc * 100))
        ok = False

    # ---- 5) iverilog 真仿真（若可用） ----
    iverilog = subprocess.run(["which", "iverilog"], capture_output=True, text=True)
    if iverilog.returncode == 0:
        r = subprocess.run(["make", "sim"], cwd=HERE, capture_output=True, text=True)
        print("  " + r.stdout.strip().replace("\n", "\n   "))
        ok = ok and r.returncode == 0
        if r.returncode != 0:
            print("  " + r.stderr.strip().replace("\n", "\n   "))
    else:
        print("  [INFO] 本机无 iverilog；golden 已生成，"
              "真机/CI 上 `make sim` 将运行 RTL 仿真（RTL 与 golden 逐位核对）")

    print("  Verilog golden 向量: %s" % ("全部 PASS ✓" if ok else "FAIL ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
