#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# beacon_rx.py — 七语言协同 · 34m 信标接收端 (lang7)
#
# 在「34 米外的第二台设备」上运行（与 vivo X300 同一 WiFi）：
#   python3 python/beacon_rx.py                        # 只收帧
#   python3 python/beacon_rx.py --a ../entangled.pdf --b ../sample2.pdf
#       # 用原始 PDF + 帧内 seed 独立重建 EPR 共享，逐字节核对 → 效度验证
#
# 注意（诚实披露）：
#   * Android 接收组播需屏幕常亮 / 多播锁（MulticastLock）；若手机收不到，
#     改用电脑 / 第二部 Termux 设备；AP 隔离(Access Point Isolation)会挡组播。
#   * 范围 34m 是设计目标，实际取决于 AP 功率与遮挡（经典电磁波）。
# ============================================================================
import argparse
import os
import socket
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LANG7 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LANG7, "micropython"))
sys.path.insert(0, os.path.join(LANG7, "python"))
from beacon_lib import parse_frame, crc16  # noqa: E402
from rust_twin import key_byte             # noqa: E402


def listen(group, port, seconds=0.0, max_frames=0, on_frame=None):
    """加入组播组接收信标帧；返回 [(parse_dict, addr), ...]"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    mreq = socket.inet_aton(group) + socket.inet_aton("0.0.0.0")
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1.0)
    frames = []
    t0 = time.time()
    print("[rx] 监听 %s:%d …（Ctrl-C 停止；--seconds 自动停止）" % (group, port))
    try:
        while True:
            if max_frames and len(frames) >= max_frames:
                break
            if seconds and time.time() - t0 >= seconds:
                break
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            p = parse_frame(data)
            frames.append((p, addr))
            if on_frame:
                on_frame(p, addr)
    except KeyboardInterrupt:
        pass
    sock.close()
    return frames


def main():
    ap = argparse.ArgumentParser(description="34m 信标接收端 (lang7)")
    ap.add_argument("--group", default="224.0.0.34")
    ap.add_argument("--port", type=int, default=34034)
    ap.add_argument("--seconds", type=float, default=0.0, help="接收时长(秒), 0=直到Ctrl-C")
    ap.add_argument("--max-frames", type=int, default=0, help="收到 N 帧后停止, 0=不限")
    ap.add_argument("--a", default=None, help="原始 PDF A（用于效度验证）")
    ap.add_argument("--b", default=None, help="原始 PDF B（用于效度验证）")
    args = ap.parse_args()

    n_ok = [0]
    n_bad = [0]

    def on(p, addr):
        if not p["crc_ok"]:
            n_bad[0] += 1
            print("[rx] seq=%s CRC 失败  ← %s" % (p.get("seq", "?"), addr[0]))
            return
        n_ok[0] += 1
        m = p["meta"]
        print("[rx] seq=%d seed=%d θ=%.4f R=%d lenA=%d lenB=%d "
              "sliceA=%dB sliceB=%dB CRC=OK  ← %s"
              % (p.get("seq", -1), m["seed"], m["theta"], m["rounds"],
                 m["lenA"], m["lenB"], len(p["slice_a"]), len(p["slice_b"]),
                 addr[0]))

    frames = listen(args.group, args.port, args.seconds, args.max_frames, on)

    all_ok = n_bad[0] == 0
    # ---- 效度验证：帧内 seed + 原始 PDF → 独立重建 EPR 共享并核对 ----
    if args.a and args.b and frames:
        a = open(args.a, "rb").read()
        b = open(args.b, "rb").read()
        n = max(len(a), len(b))
        ra = sorted(range(n), key=lambda i: (a[i % len(a)], i))
        rb = sorted(range(n), key=lambda i: (b[i % len(b)], i))
        rank_a = [0] * n
        rank_b = [0] * n
        for r in range(n):
            rank_a[ra[r]] = r
            rank_b[rb[r]] = r
        ok_a = ok_b = tot = 0
        for p, _ in frames:
            if not p["crc_ok"]:
                continue
            seed = p["meta"]["seed"]
            for r in range(min(64, len(p["slice_a"]), len(p["slice_b"]))):
                if r >= len(a) or r >= len(b):
                    continue
                tot += 1
                if p["slice_a"][r] == (a[r] ^ key_byte(seed, rank_a[r])):
                    ok_a += 1
                if p["slice_b"][r] == (b[r] ^ key_byte(seed, rank_b[r])):
                    ok_b += 1
        print("[rx] 效度验证: 重建 shareA %d/%d、shareB %d/%d 字节一致"
              % (ok_a, tot, ok_b, tot))
        all_ok = all_ok and ok_a == tot and ok_b == tot and tot > 0

    print("[rx] 结果: 收到 %d 帧, CRC 通过 %d / 失败 %d → %s"
          % (len(frames), n_ok[0], n_bad[0], "OK ✓" if all_ok else "异常 ✗"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
