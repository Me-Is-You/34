# -*- coding: utf-8 -*-
# ============================================================================
# check_beacon_mp.py — 真 MicroPython 解释器自检 (lang7)
#
# 在 vivo X300 Termux 中运行真实 MicroPython 解释器（非主机仿真）：
#   pkg install micropython
#   cd ~/34/lang7 && micropython micropython/check_beacon_mp.py
#
# 验证 beacon_lib.py 能在 MicroPython 子集下正确构建/解析信标帧，
# CRC-16 golden 与 C/Rust/Verilog 一致。
# ============================================================================
import sys

sys.path.append("micropython")
sys.path.append("python")
from beacon_lib import crc16, build_frame, parse_frame  # noqa: E402

ok = True


def check(name, cond):
    global ok
    print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
    ok = ok and cond


# 1) CRC-16/CCITT-FALSE golden（与 C 核心 ec_crc16 / Rust / Verilog 一致）
check("CRC-16 golden \"123456789\"=0x29B1", crc16(b"123456789", 0xFFFF) == 0x29B1)

# 2) 帧构建/解析往返 + CRC 校验
meta = {"seed": 34, "lenA": 64, "lenB": 64, "theta": 1.5707963268, "rounds": 8}
sa = bytes([(7 * i) & 0xFF for i in range(64)])
sb = bytes([(5 * i) & 0xFF for i in range(64)])
f = build_frame(0, meta, sa, sb)
p = parse_frame(f)
check("帧往返 CRC OK", p["crc_ok"] and p["seq"] == 0)
check("切片逐字节一致", p["slice_a"] == sa and p["slice_b"] == sb)

# 3) 坏帧被识别
bad = f[:10] + bytes([f[10] ^ 0xFF]) + f[11:]
check("单比特翻转被 CRC 捕获", not parse_frame(bad)["crc_ok"])

print("  MicroPython 真解释器自检: %s" % ("全部 PASS ✓" if ok else "FAIL ✗"))
sys.exit(0 if ok else 1)
