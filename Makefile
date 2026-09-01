# PDF 真实纠缠机 — Makefile
# Termux（安卓）默认只有 clang++，桌面通常有 g++：自动检测，无需手动指定。
CXX ?= $(shell \
  if command -v g++ >/dev/null 2>&1; then echo g++; \
  elif command -v clang++ >/dev/null 2>&1; then echo clang++; \
  else echo g++; fi)
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra

PDF_A := 核心物理构想：经典信道模拟量子通道.pdf
OUT   := entangled.pdf

all: entangle

entangle: entangle.cpp
	$(CXX) $(CXXFLAGS) -o $@ $<

# 生成伴生 PDF（便于演示纠缠）
sample2.pdf: entangle
	./entangle make-sample sample2.pdf

# 演示：把仓库里的构想 PDF 与 sample2.pdf 纠缠
demo: entangle sample2.pdf
	./entangle entangle "$(PDF_A)" sample2.pdf -o $(OUT) --report report.txt

# 验证纠缠真实性（11 项检查）
verify: entangle
	./entangle verify $(OUT) shareA.bin shareB.bin

# 一次跑完：构建 → 纠缠 → 验证
test: demo verify

# Termux（安卓手机）一键装环境
termux-setup:
	pkg update -y
	pkg install -y clang make git python
	@echo ""
	@echo "环境就绪。若需读取手机存储中的 PDF："
	@echo "  先执行一次:  termux-setup-storage   （授权后 ~/storage/shared 可访问）"

clean:
	rm -f entangle $(OUT) shareA.bin shareB.bin report.txt sample2.pdf

.PHONY: all demo verify test clean termux-setup
