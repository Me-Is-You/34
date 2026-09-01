# -*- coding: utf-8 -*-
# ============================================================================
# selfheal.py — 七语言协同 · 自研自愈算法 (lang7)
#
# 健康状态机 + 分级自愈动作：
#   健康度: ok → degraded(可自愈) / down(需重建或提示)
#   自愈动作分级:
#     L1 重试(同一参数)  → L2 调参重试(rounds/depthRounds 升级)
#                        → L3 重建(重建 socket / 重入组播 / 重新加载 .so)
#                        → L4 提示(手机侧安装依赖提示, 例如 cargo/iverilog)
#   每次自愈事件全量落日志(时间/组件/级别/动作/详情/轮次), 并统计自愈次数。
# ============================================================================
import threading
import time


class SelfHealer:
    """自愈器：probe → ok / 触发 heal(name, level, action, detail)。"""

    def __init__(self, log=None):
        self.lock = threading.Lock()
        self.events = []          # 自愈事件
        self.health = {}          # 组件 → ok/degraded/down
        self.heal_count = 0
        self.degraded_now = set()
        self.log = log

    def set(self, name, status):
        with self.lock:
            self.health[name] = status

    def heal(self, name, level, action, detail=""):
        with self.lock:
            ev = {
                "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "component": name,
                "level": level,
                "action": action,
                "detail": detail,
            }
            self.events.append(ev)
            self.heal_count += 1
            self.degraded_now.add(name)
            self.health[name] = "degraded" if level in ("L1", "L2", "L3") else "down"
        line = "[自愈 %s/%s] %s: %s %s" % (name, level, action, detail, "")
        print("   " + line.strip())
        if self.log:
            self.log.write(json_line(ev))

    def ok(self, name, detail=""):
        with self.lock:
            self.health[name] = "ok"
            self.degraded_now.discard(name)

    def snapshot(self):
        with self.lock:
            return {
                "health": dict(self.health),
                "healEvents": len(self.events),
                "healCount": self.heal_count,
            }


def json_line(d):
    import json
    return json.dumps(d, ensure_ascii=False)
