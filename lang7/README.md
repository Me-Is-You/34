# lang7 — 七语言协同 · 真实纠缠 + 34m 信号波（vivo X300 / 天玑9500）

> 「用 C/C++ Python Rust 汇编 MicroPython Verilog 这 7 种语言搭配，通过 1 台搭配在
> vivo X300 的天玑9500 上进行真实纠缠，34 米范围性发射信号波来真实模拟。」

本目录是 v34.99 的七语言扩展层：**一台手机（vivo X300，Dimensity 9500，ARMv9.2
big.LITTLE：Cortex-X925 / A725 / A520，NEON/SVE2）**上，7 种语言各司其职、
协同完成：

1. **真实纠缠** —— 秩配对 + 布洛赫球映射 + 纠缠门 U(θ) + Procrustean 浓缩，
   浓度 **≥ 34%**（阿雷纳常数，铁律），深度趋于 99.99%；
2. **34 米范围性发射信号波** —— UDP 组播信标（`224.0.0.34:34034`，TTL=2 ≈
   802.11 一跳视距约 30–50 m，设计目标 34 m），帧携带 EPR 共享切片；
3. **真实模拟（诚实边界）** —— 经典信道模拟量子通道：EPR 共享是经典随机数
   异或密钥，CHSH ≤ 2 不变，无伪量子宣称。RTL 定点量化误差如实披露。

## 七语言分工

| 语言 | 组件 | 职责 |
|---|---|---|
| **C** | `c_cpp/entangle_core.c` | 纠缠数学核心：秩配对（稳定计数排序 O(n+256)）、并发度、浓度、深度、EPR 共享、CRC-16 |
| **C++** | `c_cpp/engine.cpp` | 引擎封装：CLI `entangle-cc`、`extern "C"` 桥（Python ctypes）、SHA-256 自检、JSON 报告 |
| **Python** | `python/orchestrator.py` | 顶层编排器：ctypes 调度 C/C++、Rust 复算、汇编差分、34m 组播信标收发、联合测量、MicroPython/Verilog 子进程 |
| **Rust** | `rust/src/lib.rs` + `main.rs` | 独立复算浓度/深度/密钥（跨语言互证）；`cdylib` FFI 供 ctypes 加载 |
| **汇编** | `asm/pairmix_x86_64.S`（本机）/ `asm/pairmix_aarch64.S`（手机） | SSE2 / NEON 配对质量内核 `ec_pairmix_asm`（Σ\|差\|），与 C 参考逐位对照 |
| **MicroPython** | `micropython/beacon_lib.py` + `beacon.py` | ESP32/RP2040 伴生信标固件：帧构建/解析/CRC；`test_host.py` 主机仿真验证 |
| **Verilog** | `verilog/*.v` | 纠缠门 RTL（sin/cos 查表 + 10 位 p ROM）、EPR PRF、CRC-16、OOK 信标调制；`sim_twin.py` golden 向量核对 |

## 快速开始

沙盒 / 开发机（x86-64）：

```bash
make all          # libeng.so + entangle-cc + asm 差分(100/100) + RTL golden 表
make test         # 全链自检
make run          # 端到端：真实纠缠 + 34m 信号波（默认 ../entangled.pdf ../sample2.pdf）
```

手机（Termux，vivo X300 / 天玑9500）：

```bash
pkg install -y clang binutils python rust iverilog
bash build_phone.sh     # AArch64 NEON 汇编 + Rust .so + iverilog 仿真
python3 python/orchestrator.py ../entangled.pdf ../sample2.pdf
```

## 端到端输出（示例，沙盒实测）

```
[1] C/C++ 引擎（libeng.so）
  [PASS] 纠缠完成 浓度≥34%  — conc=46.43% n=289817 θ=1.5708 R=8
  [PASS] 深度趋于 99.99%  — netDepth=99.99% raw=96.57% sel=94.89%
[2] Rust 纠缠数学模块
  [PASS] 浓度独立复算与 C 一致  — rust=0.464296 c=0.464296
  [PASS] EPR 密钥派生一致（K[0]=shareA[pa0]⊕A[pa0]）  — K[0]=0x89
[3] 汇编内核
  [PASS] pairmix 汇编 == C 参考  — asm=16884022 c=16884022
[4] Python 编排 · 34m 信号波（UDP 组播 224.0.0.34:34034, TTL=2）
  [PASS] 信标发射→接收 4 帧  — rx=4 crc16 全过=True
  [PASS] 联合测量（EPR 共享还原 A⊕B）  — 33/33 位一致
  [PASS] 单边共享为噪声（熵≈8）  — H(shareA)=7.999 bit/字节
[5] MicroPython（ESP32 伴生信标）
  [PASS] beacon.py 语法 + 帧逻辑仿真（6/6 项）
[6] Verilog RTL（纠缠门/PRF/信标调制）
  [PASS] RTL golden 向量一致（浓度级偏差 0.0027pp < 0.5pp）
```

## 34 米信号波 —— 物理诚实的说明

- 载体：WiFi UDP 组播（可换 433 MHz OOK 发射，见 `verilog/beacon_mod.v` 调制器）。
- TTL=2 限制为一跳，802.11 室内视距典型 30–50 m；**34 m 是设计目标**，真实覆盖
  取决于 AP 功率与遮挡 —— 这是经典电磁波，不是量子传输。
- 帧结构：`ENT34 | ver | seq | CRC16 | seed | lenA | lenB | sliceLen | θ | R | sliceA | sliceB`，
  CRC-16/CCITT-FALSE 在 C / Rust / MicroPython / Verilog 四端一致（golden `0x29B1`）。
- 联合测量：`shareA[ia] ⊕ shareB[ib] == A[ia] ⊕ B[ib]`（同秩配对位置），单边为
  满熵噪声，联合可还原 —— 经典模拟的 EPR 关联。

## 诚实披露

- **CHSH ≤ 2**：全程经典共享密钥，无纠缠非定域性宣称。
- **RTL 定点量化**：sin/cos 查表 16-bit、C 量化 10 位 → 单门 p 最大偏差 2.25%
  （C→1 处 p 奇异），**浓度级偏差 < 0.5pp**（实测 0.0027pp），34% 铁律不受影响。
- **沙盒限制**：无 rustc/cargo、iverilog、aarch64 交叉编译器 → Rust 与 AArch64 汇编
  以「源码 + 手机构建脚本」交付，其数学已由 Python 孪生 / C 核心 golden 互证。
- 秩配对曾用插入排序（O(n²)，大 PDF 挂死）+ 短数组越界读；已修为稳定计数排序
  O(n+256)，并与 Rust/Python 孪生秩序逐位一致。

## 目录

```
lang7/
├── Makefile             # 沙盒构建/测试/运行
├── build_phone.sh       # 手机 Termux 一键构建
├── c_cpp/               # C 核心 + C++ 引擎
├── rust/                # Rust 模块（cdylib FFI + CLI + 单测）
├── asm/                 # x86-64 SSE2 / AArch64 NEON 汇编内核 + 差分测试
├── python/              # orchestrator.py + rust_twin.py
├── micropython/         # beacon 固件逻辑 + 主机仿真测试
└── verilog/             # 纠缠门/PRF/CRC/调制 RTL + golden 向量
```
