# -*- coding: utf-8 -*-
# ============================================================================
# beacon_lib.py — 七语言协同 · 信标帧逻辑 (lang7)
#
# 纯 Python（MicroPython 子集，CPython 同样可跑）：
#   34 米信号波帧 = MAGIC(5) + VER(1) + SEQ(4) + CRC16(2) + PAYLOAD
#   PAYLOAD = seed(8) + lenA(4) + lenB(4) + sliceLen(4) + theta(8) + rounds(4)
#             + sliceA + sliceB
# 同一算法在 C 核心 (ec_crc16) / Rust (crc16) / Verilog (crc16.v) 中复现，
# 跨语言互证。CRC-16/CCITT-FALSE。
# ============================================================================
import struct

MAGIC = b"ENT34"
MAGIC_VER = 1
CRC_INIT = 0xFFFF


def crc16(data, crc=CRC_INIT):
    """CRC-16/CCITT-FALSE（与 C/Rust/Verilog 一致）"""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def build_frame(seq, meta, slice_a, slice_b):
    """meta: dict(seed,theta,rounds,conc,...)；slice 为 bytes。"""
    payload = struct.pack(">QIIIdI", int(meta["seed"]),
                          int(meta.get("lenA", 0)), int(meta.get("lenB", 0)),
                          len(slice_a), float(meta["theta"]),
                          int(meta["rounds"]))
    payload += slice_a + slice_b
    head = MAGIC + bytes([MAGIC_VER]) + struct.pack(">I", seq)
    crc = crc16(head + payload)
    return head + struct.pack(">H", crc) + payload


def parse_frame(frame):
    """返回 dict：crc_ok / seq / meta / slice_a / slice_b；坏帧 crc_ok=False"""
    out = {"crc_ok": False}
    if len(frame) < 5 + 1 + 4 + 2 + 8 + 4 + 4 + 4 + 8 + 4:
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
    (seed, len_a, len_b, slen, theta, rounds) = struct.unpack(">QIIIdI", payload[:32])
    rest = payload[32:]
    out["seq"] = seq
    out["meta"] = {"seed": seed, "lenA": len_a, "lenB": len_b,
                   "theta": theta, "rounds": rounds, "ver": ver}
    out["slice_a"] = rest[:slen]
    out["slice_b"] = rest[slen:slen + slen]
    return out
