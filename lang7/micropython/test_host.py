#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# test_host.py — 七语言协同 · MicroPython 信标仿真验证 (lang7)
#
# 在主机上验证：
#   1) beacon.py / beacon_lib.py 语法（MicroPython 子集，py_compile 可查）
#   2) 帧构建/解析/CRC-16 与 C/Rust/Verilog golden 一致
#   3) 发射→回环接收→联合测量还原（模拟 34m 信标链路）
# ============================================================================
import io
import py_compile
import socket
import struct
import sys
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def main():
    ok = True

    # 1) 语法检查
    for f in ("beacon_lib.py", "beacon.py"):
        try:
            py_compile.compile(os.path.join(HERE, f), doraise=True)
            print("  [PASS] 语法 OK:", f)
        except Exception as e:
            print("  [FAIL] 语法:", f, e)
            ok = False

    from beacon_lib import build_frame, parse_frame, crc16

    # 2) CRC golden（与 C 核心 ec_crc16 / Rust crc16 一致）
    if crc16(b"123456789", 0xFFFF) == 0x29B1:
        print("  [PASS] CRC-16/CCITT golden: 0x29B1")
    else:
        print("  [FAIL] CRC golden 失配")
        ok = False

    # 3) 帧链路仿真（发射 → 回环接收 → 校验 → 联合测量）
    meta = {"seed": 34, "theta": 1.5707963268, "rounds": 8, "lenA": 64, "lenB": 64}
    group, port = "224.0.0.34", 34035  # 测试端口（与演示端口错开）
    sent = []
    for seq in range(3):
        sa = bytes([(seq * 7 + i * 3) & 0xFF for i in range(64)])
        sb = bytes([(seq * 5 + i * 11) & 0xFF for i in range(64)])
        f = build_frame(seq, meta, sa, sb)
        sent.append((f, sa, sb))
    # 回环发送
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("", port))
    rx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                  socket.inet_aton(group) + socket.inet_aton("0.0.0.0"))
    rx.settimeout(2.0)
    for f, _, _ in sent:
        tx.sendto(f, (group, port))
    got = []
    try:
        while len(got) < 3:
            d, _ = rx.recvfrom(4096)
            got.append(d)
    except socket.timeout:
        pass
    tx.close()
    rx.close()

    if len(got) == 3:
        print("  [PASS] 信标回环 3/3 帧")
    else:
        print("  [FAIL] 信标回环 %d/3 帧" % len(got))
        ok = False

    for i, (f, sa, sb) in enumerate(sent):
        if i >= len(got):
            break
        p = parse_frame(got[i])
        if not (p["crc_ok"] and p["slice_a"] == sa and p["slice_b"] == sb):
            print("  [FAIL] 帧 %d 内容/CRC 失配" % i)
            ok = False
            break
    else:
        print("  [PASS] 帧内容 + CRC16 逐字节一致")

    # 4) 联合测量：sa ⊕ sb == A ⊕ B（seq=2 帧，与发送公式一致）
    p2 = parse_frame(got[2])
    sa2, sb2 = p2["slice_a"], p2["slice_b"]
    expect = bytes([((2 * 7 + i * 3) ^ (2 * 5 + i * 11)) & 0xFF
                    for i in range(64)])
    if all(sa2[i] ^ sb2[i] == expect[i] for i in range(64)):
        print("  [PASS] 联合测量：shareA⊕shareB == A⊕B（seq=2）")
    else:
        print("  [FAIL] 联合测量失配")
        ok = False

    print("  MicroPython 信标仿真: %s" % ("全部 PASS ✓" if ok else "FAIL ✗"))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
