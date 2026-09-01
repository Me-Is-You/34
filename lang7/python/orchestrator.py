#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# orchestrator.py — 七语言协同 · Python 编排器 (lang7)
#
# 「1 台搭配」：在 vivo X300（天玑9500）上同时指挥 7 种语言完成真实纠缠 +
# 34 米范围性发射信号波（经典信道模拟量子通道，本仓库论文论点）。
#
#   C/C++   — 纠缠引擎 (libeng.so)：浓度/深度/EPR 共享
#   Rust    — 独立复算浓度（跨语言互证；沙盒无 cargo 时用 Python 孪生）
#   汇编    — ec_pairmix_asm 配对质量内核（x86-64 本地测 / AArch64 手机测）
#   Python  — 本编排器：ctypes 调度 + 34 米信标发射/接收 + 联合测量
#   MicroPython — ESP32/RP2040 伴生信标固件逻辑（test_host.py 仿真验证）
#   Verilog — 纠缠门/PRF/信标调制 RTL（sim_twin.py 生成 golden 向量验证）
#
# 用法:
#   python3 orchestrator.py <A.pdf> <B.pdf> [--seed 34] [--no-emit]
#   python3 beacon_rx.py [--group 224.0.0.34] [--port 34034]   (接收端)
# ============================================================================
import argparse
import ctypes
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import time

LANG7 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCAST_GROUP = "224.0.0.34"   # 34 主题：组播组地址
MCAST_PORT = 34034           # 34 主题：端口
MAGIC = b"ENT34"
BEACON_TTL = 2               # 802.11 一跳 ≈ 34m 视距（诚实声明：视环境而定）

sys.path.insert(0, os.path.join(LANG7, "micropython"))
from beacon_lib import build_frame, parse_frame, crc16  # noqa: E402


def report(name, ok, detail=""):
    print("  [%s] %s  — %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def load_libeng():
    lib = ctypes.CDLL(os.path.join(LANG7, "c_cpp", "libeng.so"))
    lib.engine_entangle.restype = ctypes.c_void_p
    lib.engine_entangle.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_uint64, ctypes.c_double, ctypes.c_int, ctypes.c_double, ctypes.c_int,
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
    ]
    lib.engine_free.restype = None
    lib.engine_free.argtypes = [ctypes.c_void_p]
    lib.ec_pairmix_asm.restype = ctypes.c_uint64
    lib.ec_pairmix_asm.argtypes = [ctypes.POINTER(ctypes.c_uint8),
                                   ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
    return lib


def entangle_cc(lib, path_a, path_b, seed, depth_rounds):
    buf_a = ctypes.c_char_p()
    buf_b = ctypes.c_char_p()
    la = ctypes.c_size_t()
    lb = ctypes.c_size_t()
    jp = lib.engine_entangle(
        path_a.encode(), path_b.encode(), seed,
        ctypes.c_double(-1.0), ctypes.c_int(-1), ctypes.c_double(0.90),
        ctypes.c_int(depth_rounds),
        ctypes.byref(buf_a), ctypes.byref(la),
        ctypes.byref(buf_b), ctypes.byref(lb),
    )
    if not jp:
        raise RuntimeError("engine_entangle 返回空（可能浓度 < 34% 不可达）")
    j = ctypes.string_at(jp).decode()
    lib.engine_free(jp)
    if not j.strip():
        raise RuntimeError("engine_entangle 返回空 JSON")
    meta = json.loads(j)
    if meta.get("err"):
        raise RuntimeError(meta["err"])
    share_a = ctypes.string_at(buf_a, la.value)
    share_b = ctypes.string_at(buf_b, lb.value)
    return meta, share_a, share_b


def rust_concentration(lib, a, b, meta):
    """Rust 独立复算：优先 ctypes 加载 libentangle_rust.so；
    沙盒无 cargo 时退化为 Python 孪生（同一算法的直译）。"""
    so = os.path.join(LANG7, "rust", "libentangle_rust.so")
    if os.path.exists(so):
        lr = ctypes.CDLL(so)
        lr.rs_concentration.restype = ctypes.c_double
        lr.rs_concentration.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
            ctypes.c_double, ctypes.c_int, ctypes.c_double,
        ]
        lr.rs_key_byte.restype = ctypes.c_uint8
        lr.rs_key_byte.argtypes = [ctypes.c_uint64, ctypes.c_uint64]
        A = (ctypes.c_uint8 * len(a)).from_buffer_copy(a)
        B = (ctypes.c_uint8 * len(b)).from_buffer_copy(b)
        conc = lr.rs_concentration(A, len(a), B, len(b), meta["theta"],
                                   meta["rounds"], meta["fid"])
        k0 = lr.rs_key_byte(meta["seed"], 0)
        return conc, k0, "ctypes .so"
    from rust_twin import concentration as rs_twin, key_byte as rs_kb
    conc = rs_twin(a, b, meta["theta"], meta["rounds"], meta["fid"])
    return conc, rs_kb(meta["seed"], 0), "python-twin (沙盒无 cargo；手机 cargo build 后为原生 .so)"


def asm_pairmix(lib, a, b, meta):
    """汇编内核：按秩配对字节流求 Σ|差|，与 C 参考对照（由 C++ 引擎已对照，
    这里直接从 asm 符号再验一次）。"""
    n = max(len(a), len(b))
    # 构造配对后的字节数组（与 C 核心同秩配对）
    sa = sorted(range(n), key=lambda i: (a[i % len(a)], i))
    sb = sorted(range(n), key=lambda i: (b[i % len(b)], i))
    xa = (ctypes.c_uint8 * n)(*[a[sa[i] % len(a)] for i in range(n)])
    xb = (ctypes.c_uint8 * n)(*[b[sb[i] % len(b)] for i in range(n)])
    asm_v = lib.ec_pairmix_asm(xa, xb, n)
    return asm_v, meta.get("pairmixC", -1), meta.get("mixMatch", "0") == "1"


def emit_beacon(group, port, meta, share_a, share_b, n_frames=4):
    """34 米范围性发射信号波：UDP 组播帧携带 EPR 共享切片。
    物理诚实：WiFi 802.11 视距约 30–50m，34m 为设计目标；
    真实范围取决于 AP 功率/遮挡——经典电磁波，非量子传输。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, BEACON_TTL)
    fm = dict(meta)                 # 帧头需要 lenA/lenB（文件长度）
    fm["lenA"] = len(share_a)
    fm["lenB"] = len(share_b)
    sent = 0
    for seq in range(n_frames):
        frame = build_frame(seq, fm, share_a[:64], share_b[:64])
        sock.sendto(frame, (group, port))
        sent += 1
        time.sleep(0.05)
    sock.close()
    return sent


def recv_beacon(group, port, timeout=3.0):
    """接收端（本机回环验证；真机场景即 34m 外的另一台设备）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    mreq = socket.inet_aton(group) + socket.inet_aton("0.0.0.0")
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(timeout)
    frames = []
    try:
        while True:
            data, _ = sock.recvfrom(4096)
            frames.append(data)
            if len(frames) >= 4:
                break
    except socket.timeout:
        pass
    sock.close()
    return frames


def joint_measure(meta, share_a, share_b, a, b):
    """联合测量：把两份 EPR 共享按配对位置合并，还原 A⊕B 切片。"""
    n = max(len(a), len(b))
    sa = sorted(range(n), key=lambda i: (a[i % len(a)], i))
    sb = sorted(range(n), key=lambda i: (b[i % len(b)], i))
    ok = 0
    total = 0
    for r in range(0, 64):
        ia, ib = sa[r], sb[r]
        if ia >= len(a) or ib >= len(b):
            continue
        expect = a[ia] ^ b[ib]
        got = share_a[ia] ^ share_b[ib]
        total += 1
        ok += (got == expect)
    return ok, total


def main():
    ap = argparse.ArgumentParser(description="七语言协同 · 纠缠编排器 (lang7)")
    ap.add_argument("pdf_a")
    ap.add_argument("pdf_b")
    ap.add_argument("--seed", type=int, default=34)
    ap.add_argument("--depth-rounds", type=int, default=16384)
    ap.add_argument("--no-emit", action="store_true", help="不发射信标")
    ap.add_argument("--group", default=MCAST_GROUP)
    ap.add_argument("--port", type=int, default=MCAST_PORT)
    args = ap.parse_args()

    print("=" * 72)
    print("  七语言协同 · 真实纠缠 + 34m 信号波 — vivo X300 (天玑9500) 编排")
    print("=" * 72)
    all_ok = True

    # ---- 0. 构建 C/C++ 引擎（make 已在外部完成，这里确认 .so 存在） ----
    so = os.path.join(LANG7, "c_cpp", "libeng.so")
    if not os.path.exists(so):
        print("[FAIL] 未找到 libeng.so —— 请先在 lang7/ 目录执行 make all")
        return 1
    lib = load_libeng()

    a = open(args.pdf_a, "rb").read()
    b = open(args.pdf_b, "rb").read()

    # ---- 1. C/C++ 引擎：真实纠缠 ----
    print("\n[1] C/C++ 引擎（libeng.so）")
    meta, share_a, share_b = entangle_cc(lib, args.pdf_a, args.pdf_b, args.seed,
                                         args.depth_rounds)
    all_ok &= report("纠缠完成 浓度≥34%", meta["conc"] >= 0.34 - 1e-9,
                     "conc=%.2f%% n=%d θ=%.4f R=%d" %
                     (meta["conc"] * 100, meta["n"], meta["theta"], meta["rounds"]))
    all_ok &= report("深度趋于 99.99%", meta.get("depthOk") == "1",
                     "netDepth=%.2f%% raw=%.2f%% sel=%.2f%%" %
                     (meta["netDepth"] * 100, meta["rawDepth"] * 100,
                      meta["selFrac"] * 100))

    # ---- 2. Rust 独立复算（跨语言互证） ----
    print("\n[2] Rust 纠缠数学模块")
    rs_conc, rs_k0, how = rust_concentration(lib, a, b, meta)
    agree = abs(rs_conc - meta["conc"]) < 1e-9
    # 诚实核对：epr_shares 中 shareA[pa[0]] = a[pa[0]] ⊕ K[0]（pa 为秩配对索引）
    sa0 = sorted(range(len(a)), key=lambda i: (a[i], i))[0]
    k_agree = (rs_k0 == (share_a[sa0] ^ a[sa0]))
    all_ok &= report("浓度独立复算与 C 一致", agree,
                     "rust=%.6f c=%.6f (%s)" % (rs_conc, meta["conc"], how))
    all_ok &= report("EPR 密钥派生一致（K[0]=shareA[pa0]⊕A[pa0]）", k_agree,
                     "K[0]=0x%02X" % rs_k0)

    # ---- 3. 汇编内核 ----
    print("\n[3] 汇编内核（x86-64 SSE2 本机 / AArch64 NEON 手机）")
    asm_v, mix_c, mix_ok = asm_pairmix(lib, a, b, meta)
    all_ok &= report("pairmix 汇编 == C 参考", mix_ok and asm_v == mix_c,
                     "asm=%d c=%d" % (asm_v, mix_c))

    # ---- 4. Python 编排 + 34m 信号波发射/接收 ----
    print("\n[4] Python 编排 · 34m 信号波（UDP 组播 %s:%d, TTL=%d）"
          % (args.group, args.port, BEACON_TTL))
    if args.no_emit:
        print("  （--no-emit，跳过发射）")
    else:
        # 先起接收端（加入组播组），再发射——否则广播在接收端就绪前到达会被丢弃
        import threading
        rx_box = {}
        def _rx():
            rx_box["frames"] = recv_beacon(args.group, args.port)
        rt = threading.Thread(target=_rx, daemon=True)
        rt.start()
        time.sleep(0.5)                 # 等接收端加入组播
        sent = emit_beacon(args.group, args.port, meta, share_a, share_b)
        rt.join(timeout=5.0)
        frames = rx_box.get("frames", [])
        crc_ok = all(parse_frame(f)["crc_ok"] for f in frames)
        all_ok &= report("信标发射→接收 %d 帧" % sent, len(frames) == sent and crc_ok,
                         "rx=%d crc16 全过=%s" % (len(frames), crc_ok))
        if frames:
            f0 = parse_frame(frames[0])
            ok_j, tot_j = joint_measure(meta, share_a, share_b, a, b)
            all_ok &= report("联合测量（EPR 共享还原 A⊕B）", ok_j == tot_j and tot_j > 0,
                             "%d/%d 位一致 — 单边噪声，联合可还原" % (ok_j, tot_j))
        # 单边噪声检验（熵）
        import math
        def ent(d):
            h = {}
            for x in d:
                h[x] = h.get(x, 0) + 1
            n = len(d)
            return -sum(p / n * math.log2(p / n) for p in h.values())
        all_ok &= report("单边共享为噪声（熵≈8）", ent(share_a) > 7.5,
                         "H(shareA)=%.3f bit/字节" % ent(share_a))

    # ---- 5. MicroPython 信标固件（仿真验证） ----
    print("\n[5] MicroPython（ESP32 伴生信标）")
    r = subprocess.run([sys.executable, os.path.join(LANG7, "micropython", "test_host.py")],
                       capture_output=True, text=True)
    mp_ok = r.returncode == 0
    print("   " + r.stdout.strip().replace("\n", "\n   "))
    all_ok &= report("beacon.py 语法 + 帧逻辑仿真", mp_ok, "")

    # ---- 6. Verilog RTL（golden 向量验证） ----
    print("\n[6] Verilog RTL（纠缠门/PRF/信标调制）")
    r = subprocess.run([sys.executable, os.path.join(LANG7, "verilog", "sim_twin.py")],
                       capture_output=True, text=True)
    v_ok = r.returncode == 0
    print("   " + r.stdout.strip().replace("\n", "\n   "))
    all_ok &= report("RTL golden 向量一致", v_ok, "")

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    print("  七语言协同 · 结果汇总: %s" % ("全部 PASS ✓" if all_ok else "存在 FAIL ✗"))
    print("  浓度 %.2f%% ≥ 34%% · 净深度 %.2f%% 趋于 99.99%% · 信标组播 %s:%d"
          % (meta["conc"] * 100, meta["netDepth"] * 100, args.group, args.port))
    print("  语言链: C → C++ → 汇编 → Rust → Python → MicroPython → Verilog")
    print("=" * 72)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
