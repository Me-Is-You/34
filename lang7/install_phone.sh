#!/usr/bin/env bash
# ============================================================================
# install_phone.sh — vivo X300 (天玑9500) Termux 一键安装 (lang7)
#
# 前置：已从 F-Droid 安装 Termux（不要用 Play 版），并执行过：
#   pkg update && pkg upgrade
#   termux-setup-storage          # 授权存储访问（拷贝仓库用）
# 用法：bash install_phone.sh
# ============================================================================
set -e

echo "============================================================"
echo " lang7 · 七语言协同安装 — vivo X300 (天玑9500) · Termux"
echo " C / C++ / Python / Rust / 汇编 / MicroPython / Verilog"
echo "============================================================"

# ---------- [1/5] pkg 源更新 ----------
echo ""
echo "[1/5] pkg update && pkg upgrade（首次较久，请保持网络通畅）"
pkg update -y || { echo "pkg update 失败：请检查网络或换源（见 INSTALL.md FAQ）"; exit 1; }
pkg upgrade -y || true

# ---------- [2/5] 安装依赖 ----------
echo ""
echo "[2/5] 安装编译/运行依赖"
pkg install -y clang binutils python rust make git iverilog || {
    echo "部分包安装失败：请检查网络/存储空间后重试，或逐包安装";
    echo "  pkg install -y clang binutils python rust make git iverilog";
    exit 1; }
# 可选：真 MicroPython 解释器（跑固件逻辑自检）
pkg install -y micropython 2>/dev/null || echo "  (可选) micropython 未装，跳过真解释器自检"
pkg install -y termux-api 2>/dev/null || true   # 可选：termux-wake-lock 长跑防休眠

# ---------- [3/5] 获取代码 ----------
echo ""
echo "[3/5] 获取仓库代码"
if [ -d "$HOME/34/lang7" ]; then
    echo "  已存在 $HOME/34/lang7，跳过克隆"
elif command -v git >/dev/null 2>&1 && \
     git ls-remote https://github.com/Me-Is-You/34.git HEAD >/dev/null 2>&1; then
    cd "$HOME"
    git clone --depth 1 https://github.com/Me-Is-You/34.git
    echo "  git clone 完成 → $HOME/34"
else
    echo "  git clone 失败（网络受限）"
    echo "  请改用拷贝方式："
    echo "    1) 电脑下载 https://github.com/Me-Is-You/34/archive/refs/heads/main.zip"
    echo "    2) 解压后把 34 文件夹放到手机 /sdcard/Download/"
    echo "    3) 执行: cp -r /sdcard/Download/34 \$HOME/34"
    exit 1
fi
cd "$HOME/34/lang7"

# ---------- [4/5] 构建 7 语言产物 ----------
echo ""
echo "[4/5] 构建（C/C++/汇编 → libeng.so + entangle-cc；Rust → .so；Verilog → 仿真）"
bash build_phone.sh || { echo "构建失败，请查看上方错误（常见问题见 INSTALL.md）"; exit 1; }

# ---------- [5/5] 全链自检 + 下一步 ----------
echo ""
echo "[5/5] 全链自检"
python3 micropython/test_host.py || true
command -v micropython >/dev/null 2>&1 && micropython micropython/check_beacon_mp.py || true

echo ""
echo "============================================================"
echo " 安装完成 ✓  下一步操作流程（详见 INSTALL.md）"
echo "------------------------------------------------------------"
echo " ① 单轮真实纠缠 + 34m 信标:"
echo "    python3 python/orchestrator.py ../entangled.pdf ../sample2.pdf"
echo " ② 持续巡回长跑 (Ctrl-C 停止出十项属性审计):"
echo "    bash tour_phone.sh"
echo " ③ 34m 范围实测 (第二台设备, 同一 WiFi):"
echo "    python3 python/beacon_rx.py --a ../entangled.pdf --b ../sample2.pdf"
echo " ④ 自愈演示 (注入故障):"
echo "    python3 python/tour.py ../entangled.pdf ../sample2.pdf --emit"
echo "        --fault-inject engine@2,beacon_tx@3 --max-rounds 5"
echo "============================================================"
