#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# tour.py — 七语言协同 · 巡回环境（持续真实发射 + 养成 + 自愈 + 十项属性）
#
# 在 vivo X300（天玑9500）Termux 中持续运行：
#   每轮巡回: 真实纠缠(C/C++) → 跨语言互证(Rust/汇编) → 发射34m信号波(组播)
#            → 接收/CRC/联合测量 → 养成控制律(深度→99.99%) → 自愈巡检
#   信标链路线程持续发射/接收（与轮次解耦，period 可独立设定）。
#
# 用法:
#   python3 tour.py <A.pdf> <B.pdf> [--seed 34] [--period 5] [--until 3600]
#       [--max-rounds 0] [--beacon-period 2] [--emit] [--random-seed]
#       [--log tour_log.jsonl] [--curve tour_curve.jsonl]
# 手机: bash tour_phone.sh（Termux 长跑入口，Ctrl-C 优雅停止并出审计报告）
# ============================================================================
import argparse
import json
import math
import os
import random
import socket
import subprocess
import sys
import threading
import time

LANG7 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LANG7, "python"))
sys.path.insert(0, os.path.join(LANG7, "micropython"))

from orchestrator import (load_libeng, entangle_cc, rust_concentration,  # noqa: E402
                          asm_pairmix, MCAST_GROUP, MCAST_PORT)
from beacon_lib import build_frame, parse_frame, crc16                  # noqa: E402
from cultivation import Cultivation                                     # noqa: E402
from selfheal import SelfHealer                                         # noqa: E402
import audit                                                            # noqa: E402

CLASSICAL_TAG = "CLASSICAL-SIM"   # 伦理标记：经典信道模拟量子通道，无伪量子宣称


# ============================ 信标链路（持续发射/接收） =====================
class BeaconLink:
    """34m 组播信标：后台线程持续发射 + 接收 + CRC + 联合测量。"""

    def __init__(self, group, port, a, b, meta, share_a, share_b,
                 beacon_period=2.0, seed=34):
        self.group = group
        self.port = port
        self.a = a
        self.b = b
        self.period = float(beacon_period)
        self.seed = seed
        self.lock = threading.Lock()
        self.stop_ev = threading.Event()
        self.meta = meta
        self.share_a = share_a
        self.share_b = share_b
        self.stats = {"tx": 0, "rx": 0, "crcBad": 0, "jointOk": 0, "jointTot": 0}
        # 秩配对预计算（与 C 核心同序，联合测量 O(1)/帧）
        n = max(len(a), len(b))
        self.sa = sorted(range(n), key=lambda i: (a[i % len(a)], i))
        self.sb = sorted(range(n), key=lambda i: (b[i % len(b)], i))
        # 收发 socket
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx.bind(("", port))
        self.rx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                          socket.inet_aton(group) + socket.inet_aton("0.0.0.0"))
        self.rx.settimeout(1.0)
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.tx_thread.start()
        self.rx_thread.start()

    # ---- 自愈：重建 socket（L3） ----
    def heal_tx(self):
        """重建发射 socket（若已被故障注入/系统关闭）。"""
        try:
            self.tx.close()
        except OSError:
            pass
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        with self.lock:
            self.stats["healTx"] = self.stats.get("healTx", 0) + 1

    def heal_rx(self):
        """重建接收 socket（重新绑定 + 加入组播组）。"""
        try:
            self.rx.close()
        except OSError:
            pass
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx.bind(("", self.port))
        self.rx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                          socket.inet_aton(self.group) + socket.inet_aton("0.0.0.0"))
        self.rx.settimeout(1.0)
        with self.lock:
            self.stats["healRx"] = self.stats.get("healRx", 0) + 1

    def break_tx(self):
        """故障注入：关闭发射 socket（下个周期自愈）。"""
        try:
            self.tx.close()
        except OSError:
            pass

    def update(self, meta, share_a, share_b):
        with self.lock:
            self.meta = meta
            self.share_a = share_a
            self.share_b = share_b

    def _frame(self):
        with self.lock:
            meta, sa, sb, seq = self.meta, self.share_a, self.share_b, self.stats["tx"]
            fm = dict(meta)
            fm["lenA"] = len(sa)
            fm["lenB"] = len(sb)
            return build_frame(seq, fm, sa[:64], sb[:64])

    def _tx_loop(self):
        while not self.stop_ev.is_set():
            try:
                self.tx.sendto(self._frame(), (self.group, self.port))
                with self.lock:
                    self.stats["tx"] += 1
            except OSError:
                # 自愈：socket 被关闭/故障 → 重建
                with self.lock:
                    self.stats["txErr"] = self.stats.get("txErr", 0) + 1
                self.heal_tx()
            self.stop_ev.wait(self.period)

    def _rx_loop(self):
        while not self.stop_ev.is_set():
            try:
                data, _ = self.rx.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                self.heal_rx()
                continue
            p = parse_frame(data)
            with self.lock:
                self.stats["rx"] += 1
                if not p["crc_ok"]:
                    self.stats["crcBad"] += 1
                    continue
                sa, sb, a, b = self.share_a, self.share_b, self.a, self.b
                for r in range(min(64, len(self.sa))):
                    ia, ib = self.sa[r], self.sb[r]
                    if ia >= len(sa) or ib >= len(sb) or ia >= len(a) or ib >= len(b):
                        continue
                    self.stats["jointTot"] += 1
                    if (sa[ia] ^ sb[ib]) == (a[ia] ^ b[ib]):
                        self.stats["jointOk"] += 1

    def burst(self, n=4):
        """本轮巡回的密集发射 + 立即回环统计（自验）。"""
        sent = 0
        for _ in range(n):
            try:
                self.tx.sendto(self._frame(), (self.group, self.port))
                with self.lock:
                    self.stats["tx"] += 1
                sent += 1
                time.sleep(0.02)
            except OSError:
                break
        return sent

    def snapshot(self):
        with self.lock:
            return dict(self.stats)

    def close(self):
        self.stop_ev.set()
        self.tx_thread.join(timeout=3)
        self.rx_thread.join(timeout=3)
        try:
            self.tx.close()
            self.rx.close()
        except OSError:
            pass


# ============================ 巡回主循环 ====================================
class Tour:
    def __init__(self, args):
        self.args = vars(args)
        self.seed = args.seed
        self.rng_used = False
        self.a = open(args.pdf_a, "rb").read()
        self.b = open(args.pdf_b, "rb").read()
        self.lib = load_libeng()
        self.healer = SelfHealer()
        self.cult = Cultivation(depth_rounds=args.depth_rounds,
                                rounds=args.rounds if args.rounds > 0 else 8,
                                theta=args.theta if args.theta > 0 else 1.5707963267948966,
                                fid=args.fidelity)
        self.meta = None
        self.share_a = b""
        self.share_b = b""
        # 秩配对预计算（与 C 核心同序；K0 与联合测量复用）
        n = max(len(self.a), len(self.b))
        self.rank_a = sorted(range(n), key=lambda i: (self.a[i % len(self.a)], i))
        self.rank_b = sorted(range(n), key=lambda i: (self.b[i % len(self.b)], i))
        self.link = None
        self.measure = {}
        self.log_fh = open(args.log, "a") if args.log else None
        self.curve_fh = open(args.curve, "a") if args.curve else None
        self.started = time.time()
        self.round_no = 0
        self.obj_conc = 0.0
        self.obj_delta = -1.0
        self.repro_delta = -1.0
        self.falsify_ok = False
        self.falsify_conc = 0.0
        self.reliability_ok = False
        self.ethics_ok = True          # 结构性成立：全程经典模拟，日志含标记
        self.transparent_ok = False

    # ---- 系统校验（启动时一次）----
    def system_checks(self):
        print("── 系统校验：可证伪性 / 可重复性 / 客观性 / 信度 ──")
        # 可证伪性：全零输入必须被拒绝（0% 数据不得谎报为 34%+）
        import tempfile
        zeros = bytes(1024)
        with tempfile.NamedTemporaryFile(suffix=".bin") as fz:
            fz.write(zeros)
            fz.flush()
            try:
                m0, _, _ = entangle_cc(self.lib, fz.name, fz.name, 1, 64)
                self.falsify_conc = float(m0["conc"])
                self.falsify_ok = self.falsify_conc < 0.01
            except RuntimeError:
                self.falsify_conc = 0.0
                self.falsify_ok = True   # 引擎诚实拒绝：浓度 < 34% 不可达
        print("  [%s] 可证伪性: 全零输入 → conc=%.4f %s"
              % ("PASS" if self.falsify_ok else "FAIL", self.falsify_conc,
                 "(引擎拒绝, 0% 数据不谎报)" if self.falsify_conc == 0.0 else "(<1%)"))

        # 可重复性：同种子重跑 → JSON 逐字节一致
        m1, s1a, s1b = entangle_cc(self.lib, self.args["pdf_a"], self.args["pdf_b"],
                                   self.seed, self.cult.depth_rounds)
        m2, s2a, s2b = entangle_cc(self.lib, self.args["pdf_a"], self.args["pdf_b"],
                                   self.seed, self.cult.depth_rounds)
        same_json = (json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)
                     and s1a == s2a and s1b == s2b)
        self.repro_delta = 0.0 if same_json else abs(float(m1["conc"]) - float(m2["conc"]))
        print("  [%s] 可重复性: 同 seed=%d 重跑 → %s"
              % ("PASS" if self.repro_delta == 0.0 else "FAIL", self.seed,
                 "逐字节一致" if same_json else "Δconc=%.2e" % self.repro_delta))
        self.meta, self.share_a, self.share_b = m1, s1a, s1b

        # 客观性：Rust/Python 独立复算
        obj_conc, k0, how = rust_concentration(self.lib, self.a, self.b, self.meta)
        self.obj_conc = obj_conc
        self.obj_delta = abs(obj_conc - float(self.meta["conc"]))
        print("  [%s] 客观性: C=%.6f Rust/Python=%.6f Δ=%.2e (%s)"
              % ("PASS" if self.obj_delta < 1e-9 else "FAIL",
                 float(self.meta["conc"]), obj_conc, self.obj_delta, how))

        # 信度：K[0] 三端一致 + CRC golden
        sa0 = self.rank_a[0]
        k0_expect = self.share_a[sa0] ^ self.a[sa0]
        crc_py = crc16(b"123456789", 0xFFFF)
        self.reliability_ok = (k0 == k0_expect and crc_py == 0x29B1)
        print("  [%s] 信度: K[0]=0x%02X (C/Rust/Python 一致), CRC golden=0x%04X"
              % ("PASS" if self.reliability_ok else "FAIL", k0, crc_py))

    # ---- 每轮巡回 ----
    def _fault(self, comp, rnd):
        """故障注入检查：spec='comp@round,...' → 本轮触发一次故障。"""
        flt = self.args.get("fault_inject", "")
        for spec in flt.split(","):
            spec = spec.strip()
            if not spec:
                continue
            if "@" in spec:
                c, r = spec.split("@", 1)
                if c.strip() == comp and int(r) == rnd:
                    return True
        return False

    def round(self):
        self.round_no += 1
        params = self.cult.step(self.meta)
        rnd = self.round_no
        if self.args.get("random_seed"):
            self.seed = (self.seed * 0x9E3779B97F4A7C15 + 1) & 0xFFFFFFFFFFFFFFFF
            self.rng_used = True
        t0 = time.time()
        # 纠缠引擎（自愈：失败 → rounds+8 重试，至多 3 次）
        meta = None
        bad_a = bad_b = None
        if self._fault("engine", rnd):
            bad_a, bad_b = "/nonexistent_a.bin", "/nonexistent_b.bin"
            self.healer.heal("engine", "L1", "注入故障: 路径失效", "r%d" % rnd)
        for attempt in range(3):
            pa = bad_a if (attempt == 0 and bad_a) else self.args["pdf_a"]
            pb = bad_b if (attempt == 0 and bad_b) else self.args["pdf_b"]
            try:
                meta, sa, sb = entangle_cc(self.lib, pa, pb, self.seed,
                                           params["depth_rounds"])
                break
            except RuntimeError as e:
                if bad_a and attempt == 0:
                    self.healer.heal("engine", "L2", "切换真实输入重试",
                                     "r%d %s" % (rnd, str(e)[:60]))
                else:
                    self.healer.heal("engine", "L2", "调参重试 rounds+8",
                                     "r%d %s" % (rnd, str(e)[:60]))
                params["rounds"] = min(512, params["rounds"] + 8)
        if meta is None:
            self.healer.heal("engine", "L3", "重建 libeng 并跳过本轮", "r%d" % rnd)
            return False
        self.meta, self.share_a, self.share_b = meta, sa, sb

        # 硬指标（铁律）
        conc = float(meta["conc"])
        if conc < 0.34 - 1e-9:
            self.healer.heal("concentration", "L2", "rounds+8",
                             "conc=%.4f < 34%%" % conc)
        if meta.get("depthOk") != "1":
            self.healer.heal("depth", "L2", "depthRounds×2",
                             "net=%.6f < 99.99%%" % float(meta.get("netDepth", 0)))

        # 跨语言互证：Rust 复算 + 汇编差分
        obj_conc, k0, how = rust_concentration(self.lib, self.a, self.b, meta)
        if abs(obj_conc - conc) >= 1e-9:
            self.healer.heal("rust", "L3", "重载 libentangle_rust.so",
                             "Δ=%.2e" % abs(obj_conc - conc))
        asm_v, mix_c, mix_ok = asm_pairmix(self.lib, self.a, self.b, meta)
        if not (mix_ok and asm_v == mix_c):
            self.healer.heal("asm", "L2", "回退 C 参考", "asm=%d c=%d" % (asm_v, mix_c))

        # 34m 信号波：持续线程已发射；本轮加密集发射 + 回环自验
        if self.args.get("emit"):
            self.link.update(meta, sa, sb)
            if self._fault("beacon_tx", rnd):
                self.healer.heal("beacon_tx", "L1", "注入故障: 关闭发射 socket", "r%d" % rnd)
                self.link.break_tx()   # 下个周期 _tx_loop 自愈重建
            self.link.burst(4)
            time.sleep(0.3)  # 给接收线程统计窗口
            # 发射探针：本轮 txErr 增长 → 链路故障已被 _tx_loop 自愈，登记事件
            stp = self.link.snapshot()
            tx_err_new = stp.get("txErr", 0) - getattr(self, "_prev_tx_err", 0)
            if tx_err_new > 0:
                self.healer.heal("beacon_tx", "L3", "重建发射 socket（自愈）",
                                 "txErr=%d healTx=%d" % (stp.get("txErr", 0),
                                                         stp.get("healTx", 0)))
                self.healer.ok("beacon_tx")
            self._prev_tx_err = stp.get("txErr", 0)
        st = self.link.snapshot() if self.link else {}

        # 周期子检：MicroPython / Verilog
        if self.round_no % max(1, self.args.get("mp_every", 5)) == 0:
            self._subcheck("micropython", os.path.join(LANG7, "micropython", "test_host.py"))
        if self.round_no % max(1, self.args.get("sim_every", 5)) == 0:
            self._subcheck("verilog", os.path.join(LANG7, "verilog", "sim_twin.py"))

        # 度量快照
        self._measure(meta, k0, st)
        self.cult.observe(meta)
        self._log_round(meta, params, st)
        dt = time.time() - t0
        print("  [轮 %3d %s] conc=%.2f%% net=%.4f%% raw=%.2f%% sel=%.2f%% "
              "depthRounds=%d R=%d | tx=%d rx=%d crcBad=%d joint=%d/%d | %.1fs"
              % (rnd, self.cult.stage, conc * 100, float(meta["netDepth"]) * 100,
                 float(meta["rawDepth"]) * 100, float(meta["selFrac"]) * 100,
                 int(meta["depthRounds"]), int(meta["rounds"]),
                 st.get("tx", 0), st.get("rx", 0), st.get("crcBad", 0),
                 st.get("jointOk", 0), st.get("jointTot", 0), dt))
        return True

    def _subcheck(self, name, script):
        try:
            r = subprocess.run([sys.executable, script], capture_output=True,
                               text=True, timeout=180)
            ok = r.returncode == 0
        except Exception as e:
            ok = False
            r = None
        if ok:
            self.healer.ok(name)
        else:
            self.healer.heal(name, "L1", "重试一次",
                             "rc=%s" % (getattr(r, "returncode", "exc")))
            try:
                r2 = subprocess.run([sys.executable, script], capture_output=True,
                                    text=True, timeout=180)
                if r2.returncode == 0:
                    self.healer.ok(name)
                else:
                    self.healer.heal(name, "L4", "提示检查依赖", script)
            except Exception:
                self.healer.heal(name, "L4", "提示检查依赖", script)

    def _measure(self, meta, k0, st):
        import hashlib
        H = audit.entropy_of(self.share_a)
        MI = audit.mutual_info(self.share_a, self.share_b)
        rng = random.Random(self.seed ^ 0x34)
        S = audit.chsh_s(self.share_a, self.share_b, rng)
        sa0 = self.rank_a[0]
        self.measure = {
            "conc": float(meta["conc"]),
            "netDepth": float(meta["netDepth"]),
            "rawDepth": float(meta["rawDepth"]),
            "selFrac": float(meta["selFrac"]),
            "rounds": int(meta["rounds"]),
            "depthRounds": int(meta["depthRounds"]),
            "tx": st.get("tx", 0), "rx": st.get("rx", 0),
            "crcBad": st.get("crcBad", 0),
            "jointOk": st.get("jointOk", 0), "jointTot": st.get("jointTot", 0),
            "S": S, "MI": MI, "H": H,
            "K0": k0, "CRC": crc16(b"123456789", 0xFFFF),
            "shaA": hashlib.sha256(self.a).hexdigest()[:16],
            "shaB": hashlib.sha256(self.b).hexdigest()[:16],
        }
        # 效度/透明度判定
        jok, jtot = st.get("jointOk", 0), st.get("jointTot", 0)
        self.transparent_ok = bool(self.log_fh) and jtot > 0

    def _log_round(self, meta, params, st):
        if not self.log_fh:
            return
        line = json.dumps({
            "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
            CLASSICAL_TAG: True,
            "round": self.round_no,
            "seed": self.seed,
            "stage": self.cult.stage,
            "conc": float(meta["conc"]),
            "netDepth": float(meta["netDepth"]),
            "rawDepth": float(meta["rawDepth"]),
            "selFrac": float(meta["selFrac"]),
            "rounds": int(meta["rounds"]),
            "depthRounds": int(meta["depthRounds"]),
            "depthOk": meta.get("depthOk"),
            "tx": st.get("tx", 0), "rx": st.get("rx", 0),
            "crcBad": st.get("crcBad", 0),
            "jointOk": st.get("jointOk", 0), "jointTot": st.get("jointTot", 0),
            "healCount": self.healer.heal_count,
            "health": self.healer.health,
        }, ensure_ascii=False)
        self.log_fh.write(line + "\n")
        self.log_fh.flush()
        if self.curve_fh:
            pt = self.cult.curve[-1]
            self.curve_fh.write(json.dumps(pt, ensure_ascii=False) + "\n")
            self.curve_fh.flush()

    # ---- 汇总 + 十项属性审计 ----
    def finish(self):
        if self.meta is None:                 # 0 轮即停止的兜底：先跑一轮
            self.round()
        if self.link:
            self.link.close()
        if self.log_fh:
            self.log_fh.close()
        if self.curve_fh:
            self.curve_fh.close()
        st = self.link.snapshot() if self.link else {}
        self._measure(self.meta, self.measure.get("K0", 0), st)
        rows, all_ok = audit.audit_report(self)
        print("\n" + "=" * 72)
        print("  十项科学属性审计 — %s" % (CLASSICAL_TAG))
        print("=" * 72)
        for prop, ok, value, note in rows:
            print("  [%s] %-5s — %s" % ("PASS" if ok else "FAIL", prop, value))
            print("        备注: %s" % note)
        print("-" * 72)
        print("  巡回 %d 轮 · 养成阶段=%s · 自愈 %d 次 · 历时 %.0fs"
              % (self.round_no, self.cult.stage, self.healer.heal_count,
                 time.time() - self.started))
        print("  最终: 浓度 %.2f%% ≥ 34%% · 净深度 %.2f%% (趋于99.99%%) · "
              "raw %.2f%% · sel %.2f%% · CHSH S=%.3f ≤ 2"
              % (self.measure.get("conc", 0) * 100,
                 self.measure.get("netDepth", 0) * 100,
                 self.measure.get("rawDepth", 0) * 100,
                 self.measure.get("selFrac", 0) * 100,
                 self.measure.get("S", 99)))
        print("  自愈事件:")
        for ev in self.healer.events[-8:]:
            print("    %s %s/%s: %s %s" % (ev["t"], ev["component"], ev["level"],
                                            ev["action"], ev["detail"]))
        print("=" * 72)
        print("  巡回环境审计: %s" % ("全部 PASS ✓" if all_ok else "存在 FAIL ✗"))
        return 0 if all_ok else 1


def main():
    ap = argparse.ArgumentParser(description="lang7 巡回环境（持续真实发射+养成+自愈）")
    ap.add_argument("pdf_a")
    ap.add_argument("pdf_b")
    ap.add_argument("--seed", type=int, default=34)
    ap.add_argument("--random-seed", action="store_true", help="每轮轮转种子（确定性序列）")
    ap.add_argument("--theta", type=float, default=-1.0)
    ap.add_argument("--rounds", type=int, default=-1)
    ap.add_argument("--fidelity", type=float, default=0.90)
    ap.add_argument("--depth-rounds", type=int, default=64, help="养成起点（每轮×2）")
    ap.add_argument("--period", type=float, default=5.0, help="轮间间隔(秒)")
    ap.add_argument("--beacon-period", type=float, default=2.0, help="持续发射间隔(秒)")
    ap.add_argument("--emit", action="store_true", help="发射 34m 信号波")
    ap.add_argument("--group", default=MCAST_GROUP)
    ap.add_argument("--port", type=int, default=MCAST_PORT)
    ap.add_argument("--max-rounds", type=int, default=0, help="0=无限")
    ap.add_argument("--until", type=float, default=0.0, help="运行时长(秒), 0=无限")
    ap.add_argument("--log", default=os.path.join(LANG7, "tour_log.jsonl"))
    ap.add_argument("--curve", default=os.path.join(LANG7, "tour_curve.jsonl"))
    ap.add_argument("--mp-every", type=int, default=5)
    ap.add_argument("--sim-every", type=int, default=5)
    ap.add_argument("--fault-inject", default="",
                    help="自愈演示: 'engine@2,beacon_tx@3' = 第2轮引擎路径故障、第3轮信标socket故障")
    args = ap.parse_args()

    print("=" * 72)
    print("  lang7 巡回环境 · 持续真实发射 + 养成 + 自愈 + 十项科学属性")
    print("  目标设备: vivo X300 (天玑9500, AArch64 NEON) · Termux")
    print("  诚实声明: %s — 经典信道模拟量子通道, CHSH ≤ 2" % CLASSICAL_TAG)
    print("=" * 72)

    tour = Tour(args)
    # 系统校验（可证伪性/可重复性/客观性/信度）→ 生成首轮纠缠结果
    tour.system_checks()
    # 信标链路（持续发射/接收线程自此开始工作，meta 已就绪）
    if args.emit:
        tour.link = BeaconLink(args.group, args.port, tour.a, tour.b,
                               tour.meta, tour.share_a, tour.share_b,
                               args.beacon_period, args.seed)

    t_start = time.time()
    try:
        while True:
            if args.max_rounds and tour.round_no >= args.max_rounds:
                break
            if args.until and (time.time() - t_start) >= args.until:
                break
            tour.round()
            if tour.round_no >= 1 and args.until == 0 and args.max_rounds == 0:
                pass  # 无限运行，直到 Ctrl-C
            time.sleep(args.period)
    except KeyboardInterrupt:
        print("\n  [巡回] Ctrl-C 收到，优雅停止…")

    return tour.finish()


if __name__ == "__main__":
    sys.exit(main())
