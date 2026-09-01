# PDF 真实纠缠机 — Makefile
CXX      ?= g++
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

clean:
	rm -f entangle $(OUT) shareA.bin shareB.bin report.txt sample2.pdf

.PHONY: all demo verify test clean
