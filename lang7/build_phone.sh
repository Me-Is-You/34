#!/usr/bin/env bash
# ============================================================================
# build_phone.sh — vivo X300（天玑9500, AArch64）七语言一键构建
#
# 在手机 Termux 中运行：
#   pkg install -y clang binutils python rust iverilog
#   bash build_phone.sh
#
# 产物：
#   c_cpp/libeng.so          C + C++ + AArch64 NEON 汇编 融合引擎
#   entangle-cc              独立 CLI
#   rust/libentangle_rust.so Rust 原生库（orchestrator 优先 ctypes 加载）
#   verilog/sim_tb           RTL 仿真（iverilog）
# 然后：
#   python3 python/orchestrator.py ../entangled.pdf ../sample2.pdf
# ============================================================================
set -e
cd "$(dirname "$0")"
echo "=== lang7 · vivo X300 (天玑9500) 七语言构建 ==="

# 1) C/C++/汇编（AArch64 NEON）
echo "[1/4] C + C++ + 汇编 (AArch64 NEON)"
mkdir -p build
cc  -O2 -std=c11 -Wall -fPIC -c c_cpp/entangle_core.c -o build/entangle_core.o
cc  -O2 -Wall -fPIC -c asm/pairmix_aarch64.S -o build/pairmix.o
c++ -O2 -std=c++17 -Wall -fPIC -c c_cpp/engine.cpp -o build/engine.o
c++ -shared -o c_cpp/libeng.so build/engine.o build/entangle_core.o build/pairmix.o -lm
c++ -o entangle-cc build/engine.o build/entangle_core.o build/pairmix.o -lm
echo "  -> c_cpp/libeng.so + entangle-cc ✓"

# 2) Rust（Termux: pkg install rust）
echo "[2/4] Rust"
if command -v cargo >/dev/null 2>&1; then
    (cd rust && cargo build --release --target aarch64-linux-android 2>/dev/null \
      || cargo build --release) \
      && cp rust/target/release/libentangle_rust.so rust/libentangle_rust.so 2>/dev/null \
      || cp rust/target/aarch64-linux-android/release/libentangle_rust.so rust/libentangle_rust.so
    echo "  -> rust/libentangle_rust.so ✓"
else
    echo "  [skip] 无 cargo，先: pkg install rust"
fi

# 3) Verilog 仿真（Termux: pkg install iverilog）
echo "[3/4] Verilog"
if command -v iverilog >/dev/null 2>&1; then
    (cd verilog && python3 sim_twin.py && iverilog -o sim_tb tb_entangle.v epr_prf.v crc16.v entangle_gate.v beacon_mod.v && ./sim_tb)
else
    echo "  [skip] 无 iverilog，先: pkg install iverilog"
fi

# 4) 全链自检
echo "[4/4] 自检"
./build/asmtest 2>/dev/null || true
python3 micropython/test_host.py
echo "=== 构建完成 ==="
echo "  单轮编排:  python3 python/orchestrator.py ../entangled.pdf ../sample2.pdf"
echo "  巡回长跑:  bash tour_phone.sh            (Ctrl-C 停止并出十项属性审计)"
echo "  自愈演示:  python3 python/tour.py ../entangled.pdf ../sample2.pdf --emit"
echo "             --fault-inject 'engine@2,beacon_tx@3' --max-rounds 5"
