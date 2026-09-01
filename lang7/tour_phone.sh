#!/usr/bin/env bash
# ============================================================================
# tour_phone.sh — vivo X300 (天玑9500) Termux 巡回环境长跑入口
#
# 用法:
#   bash build_phone.sh          # 先构建 7 语言产物
#   bash tour_phone.sh           # 持续运行（Ctrl-C 停止并出审计报告）
#   bash tour_phone.sh 3600      # 运行 1 小时后自动停止
#   TOUR_RANDOM_SEED=1 bash tour_phone.sh   # 随机化种子（轮转，可复现序列）
# ============================================================================
set -e
cd "$(dirname "$0")"

UNTIL="${1:-0}"                     # 运行秒数, 0 = 无限直到 Ctrl-C
RANDOM_FLAG=""
[ "$TOUR_RANDOM_SEED" = "1" ] && RANDOM_FLAG="--random-seed"

echo "=== lang7 巡回环境 · vivo X300 (天玑9500) · Termux ==="
echo "    持续真实发射 34m 信号波 (224.0.0.34:34034) · 养成模型 · 自研自愈算法"
echo "    Ctrl-C 优雅停止 → 十项科学属性审计报告"
echo "    CLASSICAL-SIM: 经典信道模拟量子通道, CHSH ≤ 2, 无伪量子宣称"
echo ""

exec python3 python/tour.py \
    ../entangled.pdf ../sample2.pdf \
    --emit --beacon-period 2 --period 5 \
    --until "$UNTIL" $RANDOM_FLAG \
    --log tour_log.jsonl --curve tour_curve.jsonl
