# -*- coding: utf-8 -*-
# ============================================================================
# cultivation.py — 七语言协同 · 养成模型 (lang7)
#
# 养成 = 把纠缠资源逐轮“养成”到目标区并自维持：
#   * 目标区：净深度 netDepth ≥ 99.99%（深度趋于 99.99%）、浓度 conc ≥ 34%
#   * 成长律：depthRounds 逐轮 ×2（64 → 65536），rawDepth / selFrac 单调增长
#     （实测：raw 0.818→0.978，sel 0.575→0.963，net 恒 99.99%）
#   * 维持律：conc < 34% → rounds +8（引擎已内建自动补轮次，这里是双保险）
#   * 成熟判据：depthRounds 到顶且连续 K 轮指标在界内 → 养成完成·自维持
# 纯函数/状态机，便于单测与跨语言移植。
# ============================================================================
import json
import os

ARENA = 0.34
TARGET_DEPTH = 0.9999
MAX_DEPTH_ROUNDS = 65536
MAX_ROUNDS = 512
MATURE_KEEP = 5          # 连续 K 轮达标 → 成熟
DEFAULT_DEPTH_ROUNDS = 64


class Cultivation:
    """养成状态机：step(meta) → 下一轮引擎参数 + 阶段。"""

    def __init__(self, depth_rounds=DEFAULT_DEPTH_ROUNDS, rounds=8,
                 theta=1.5707963267948966, fid=0.90, keep=MATURE_KEEP):
        self.depth_rounds = int(depth_rounds)
        self.rounds = int(rounds)
        self.theta = float(theta)
        self.fid = float(fid)
        self.keep = int(keep)
        self.stage = "growth"          # growth → sustain → mature
        self.sustain_count = 0
        self.curve = []                # 养成曲线 [(round, net, raw, sel, conc, dr)]
        self.round_no = 0

    # ---- 成长控制律 ----
    def step(self, meta):
        """输入上一轮 meta（None 为首轮），决定本轮引擎参数。"""
        self.round_no += 1
        if meta is not None:
            conc = float(meta.get("conc", 0.0))
            if conc < ARENA - 1e-9:
                self.rounds = min(MAX_ROUNDS, self.rounds + 8)
            dr = int(meta.get("depthRounds", self.depth_rounds))
            if dr < MAX_DEPTH_ROUNDS:
                self.depth_rounds = min(MAX_DEPTH_ROUNDS, dr * 2)
            self._advance_stage(meta)
        return self.params()

    def _advance_stage(self, meta):
        net = float(meta.get("netDepth", 0.0))
        conc = float(meta.get("conc", 0.0))
        ok = (net >= TARGET_DEPTH - 1e-12 and conc >= ARENA - 1e-9
              and self.depth_rounds >= MAX_DEPTH_ROUNDS)
        if ok:
            self.sustain_count += 1
            if self.stage == "growth":
                self.stage = "sustain"
            if self.sustain_count >= self.keep:
                self.stage = "mature"
        else:
            self.sustain_count = 0
            if self.stage != "growth":
                self.stage = "growth"

    def observe(self, meta):
        """记录养成曲线点（每轮调用）。"""
        self.curve.append({
            "round": self.round_no,
            "netDepth": float(meta.get("netDepth", 0.0)),
            "rawDepth": float(meta.get("rawDepth", 0.0)),
            "selFrac": float(meta.get("selFrac", 0.0)),
            "conc": float(meta.get("conc", 0.0)),
            "depthRounds": int(meta.get("depthRounds", self.depth_rounds)),
            "stage": self.stage,
        })

    def params(self):
        return {
            "depth_rounds": self.depth_rounds,
            "rounds": self.rounds,
            "theta": self.theta,
            "fid": self.fid,
        }

    def summary(self):
        return {
            "stage": self.stage,
            "sustainCount": self.sustain_count,
            "finalDepthRounds": self.depth_rounds,
            "finalRounds": self.rounds,
            "curveLen": len(self.curve),
        }

    def save_curve(self, path):
        with open(path, "w") as f:
            for pt in self.curve:
                f.write(json.dumps(pt, ensure_ascii=False) + "\n")
