# ============================================================================
# lang7/Makefile — 七语言协同构建（C / C++ / Python / Rust / 汇编 / MicroPython / Verilog）
#
# 单一运行目标：vivo X300（天玑9500，AArch64 NEON）。
# 沙盒（x86-64）构建用 x86-64 SSE 汇编；手机 Termux 用 build_phone.sh（AArch64 NEON）。
#
#   make all      → libeng.so + entangle-cc + asm 差分测试 + RTL golden 表
#   make libeng   → C/C++/汇编 融合共享库（orchestrator 依赖）
#   make asm      → 汇编 vs C 差分测试（x86-64 本机 / AArch64 手机）
#   make rust     → cargo build --release（有 cargo 时；手机构建路径见 build_phone.sh）
#   make sim      → Verilog golden 向量 + iverilog RTL 仿真（有 iverilog 时）
#   make test     → 全链自检（asm + MicroPython + Verilog + Rust 测试）
#   make run      → orchestrator.py 端到端（默认用仓库两个 PDF）
# ============================================================================
CC      ?= gcc
CXX     ?= g++
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra -fPIC
CXXFLAGS?= -O2 -std=c++17 -Wall -Wextra -fPIC
LDLIBS  := -lm

ASM_SRC := asm/pairmix_x86_64.S
# 手机（Termux, AArch64）请用 build_phone.sh 覆盖：make ASM_SRC=asm/pairmix_aarch64.S

CORE_O  := build/entangle_core.o
ENGINE_O:= build/engine.o
ASM_O   := build/pairmix.o

PDF_A   ?= ../entangled.pdf
PDF_B   ?= ../sample2.pdf

.PHONY: all libeng entangle-cc asm rust sim test run clean

all: libeng entangle-cc asm sim
	@echo "[lang7] make all 完成：C/C++/汇编/Rust源/MicroPython源/Verilog 均已就绪"

# ---------- 目录 ----------
build:
	@mkdir -p build

# ---------- C 核心 + C++ 引擎 + 汇编 → libeng.so ----------
$(CORE_O): c_cpp/entangle_core.c c_cpp/entangle_core.h | build
	$(CC) $(CFLAGS) -c $< -o $@

$(ASM_O): $(ASM_SRC) | build
	$(CC) $(CFLAGS) -c $< -o $@

$(ENGINE_O): c_cpp/engine.cpp c_cpp/entangle_core.h | build
	$(CXX) $(CXXFLAGS) -c $< -o $@

libeng: $(ENGINE_O) $(CORE_O) $(ASM_O)
	$(CXX) -shared -o c_cpp/libeng.so $(ENGINE_O) $(CORE_O) $(ASM_O) $(LDLIBS)
	@echo "[libeng] c_cpp/libeng.so 已生成（C + C++ + 汇编融合）"

# ---------- C++ CLI ----------
entangle-cc: $(ENGINE_O) $(CORE_O) $(ASM_O)
	$(CXX) -o entangle-cc $(ENGINE_O) $(CORE_O) $(ASM_O) $(LDLIBS)
	@echo "[entangle-cc] 独立 CLI 已生成（用法: ./entangle-cc A.pdf B.pdf ...）"

# ---------- 汇编差分测试（100 组随机 + 全 PASS） ----------
asm: $(ASM_O) $(CORE_O)
	$(CC) $(CFLAGS) -c asm/harness.c -o build/harness.o
	$(CC) -o build/asmtest build/harness.o $(CORE_O) $(ASM_O) $(LDLIBS)
	./build/asmtest

# ---------- Rust（cargo 可用时） ----------
rust:
	@if command -v cargo >/dev/null 2>&1; then \
		cd rust && cargo build --release && \
		cp target/release/libentangle_rust.so libentangle_rust.so && \
		echo "[rust] libentangle_rust.so 已生成"; \
	else \
		echo "[rust] 沙盒无 cargo；源码在 rust/，手机 Termux: pkg install rust && make rust"; \
	fi

# ---------- Verilog：golden 表 + 真仿真（有 iverilog 时） ----------
sim:
	cd verilog && python3 sim_twin.py
	@if command -v iverilog >/dev/null 2>&1; then \
		cd verilog && iverilog -o sim_tb tb_entangle.v epr_prf.v crc16.v entangle_gate.v beacon_mod.v && ./sim_tb; \
	else \
		echo "[sim] 本机无 iverilog；golden 向量已生成，手机 Termux: pkg install iverilog && make sim"; \
	fi

# ---------- 全链自检 ----------
test: asm
	python3 micropython/test_host.py
	cd verilog && python3 sim_twin.py
	$(MAKE) -s rust
	@echo "[lang7] 全链自检完成"

# ---------- 端到端编排（真实纠缠 + 34m 信号波） ----------
run: libeng
	python3 python/orchestrator.py $(PDF_A) $(PDF_B)

# ---------- 巡回环境（持续真实发射 + 养成 + 自愈 + 十项属性） ----------
# 用法: make tour TOUR_ROUNDS=12 TOUR_EMIT=1
TOUR_ROUNDS ?= 0
TOUR_EMIT   ?= 1
tour: libeng
	python3 python/tour.py $(PDF_A) $(PDF_B) $(if $(filter 1,$(TOUR_EMIT)),--emit) \
		--max-rounds $(TOUR_ROUNDS) --period 3 --beacon-period 2 \
		--log tour_log.jsonl --curve tour_curve.jsonl

# ---------- 清理 ----------
clean:
	rm -rf build c_cpp/libeng.so entangle-cc rust/libentangle_rust.so
	rm -f verilog/sine.mem verilog/p_rom.mem verilog/golden_key.mem verilog/golden_p.mem verilog/sim_tb
