# lang7 安装与运行操作手册
### vivo X300（天玑9500）· Termux · 七语言协同 · 持续巡回实验

> 目标：**一台 vivo X300** 上，用 C/C++、Python、Rust、汇编、MicroPython、Verilog
> **7 种语言协同**完成真实纠缠 + **34 米范围性发射信号波**（真实模拟），并**持续运行**
> 巡回环境：养成模型、自研自愈算法、十项科学属性、深度趋于 99.99%。
>
> 诚实声明：全程 **CLASSICAL-SIM** —— 经典信道模拟量子通道，CHSH ≤ 2，无伪量子宣称。

---

## 0. 总览（读这一节就够了）

| 阶段 | 做什么 | 大约耗时 |
|---|---|---|
| **一、安装** | Termux + 依赖 + 代码 | 10–30 分钟（首次 pkg 更新慢） |
| **二、构建** | 7 语言编译产物 + 自检 | 5–15 分钟（Rust 首次编译最久） |
| **三、运行** | 单轮 → 巡回长跑 → 34m 实测 | 持续运行，Ctrl-C 停止 |

```bash
# 一键安装 + 构建 + 自检（见第 2–4 节）
bash install_phone.sh
# 之后直接：
bash tour_phone.sh        # 持续巡回（真实发射 34m 信标 + 养成 + 自愈）
```

---

## 1. 环境准备

### 1.1 安装 Termux（F-Droid 版）
1. 用手机浏览器访问 **F-Droid** 官网（f-droid.org）下载 F-Droid APK 并安装；
   ⚠️ 不要用 Google Play 商店版（已停止维护，包源过期）。
2. 在 F-Droid 里搜索 **Termux** 并安装。
3. 打开 Termux，等它初始化（自动下载 ~1GB 运行环境，需几分钟）。

### 1.2 Termux 基础配置
```bash
# 更新包源（首次务必执行）
pkg update -y && pkg upgrade -y

# 授权存储访问（会弹系统权限框，点允许）
termux-setup-storage

# 长跑防休眠（巡回实验建议开；需 termux-api 包）
pkg install -y termux-api
termux-wake-lock

# 可选：清华源加速（国内网络慢时强烈建议）
#   nano $PREFIX/etc/apt/sources.list
#   把前两行替换为：
#   deb https://mirrors.tuna.tsinghua.edu.cn/termux/termux-main stable main
#   然后 pkg update -y
```

> 天玑9500 是 64 位 ARMv9.2，Termux 自动使用 `aarch64` 架构，无需配置。

---

## 2. 获取代码（二选一）

**方式 A：git clone（推荐，可随时更新）**
```bash
pkg install -y git
cd ~
git clone --depth 1 https://github.com/Me-Is-You/34.git
cd 34/lang7
```

**方式 B：电脑拷贝（网络受限时）**
1. 电脑下载 <https://github.com/Me-Is-You/34/archive/refs/heads/main.zip>；
2. 解压得到 `34` 文件夹，拷入手机 `/sdcard/Download/`；
3. Termux 中：
```bash
cp -r /sdcard/Download/34 ~/34
cd ~/34/lang7
```

---

## 3. 一键安装（install_phone.sh）

```bash
cd ~/34/lang7
bash install_phone.sh
```

脚本自动完成：`pkg update/upgrade` → 安装 `clang binutils python rust make git iverilog`
（可选 `micropython`）→ 获取代码 → `build_phone.sh` 构建 → 全链自检 → 打印下一步。

**手动等价命令**（不想用脚本时逐条执行）：

| 语言 | 安装包 | 用途 |
|---|---|---|
| C / C++ | `clang`（含 cc/c++） | 编译 entangle_core.c / engine.cpp |
| 汇编 | `binutils` | AArch64 NEON 汇编 as/ld |
| Python | `python` | 编排器 / 巡回环境 |
| Rust | `rust`（含 cargo） | libentangle_rust.so |
| 构建工具 | `make` | Makefile 目标 |
| 代码 | `git` | 拉取仓库 |
| Verilog | `iverilog` | RTL 仿真 |
| MicroPython(可选) | `micropython` | 真解释器跑固件逻辑自检 |

---

## 4. 构建 7 语言产物

```bash
cd ~/34/lang7
bash build_phone.sh
```

各语言产物与验证（预期输出）：

| # | 语言 | 产物 / 验证 | 预期 |
|---|---|---|---|
| 1 | **C** | `entangle_core.c` → `build/entangle_core.o` | 编译无错 |
| 2 | **C++** | `engine.cpp` → `c_cpp/libeng.so` + `entangle-cc` | 链接无错 |
| 3 | **汇编** | `pairmix_aarch64.S`(NEON) → `build/pairmix.o`，差分测试 | `汇编内核 vs C 参考: 全部一致 ✓`（100 组随机） |
| 4 | **Rust** | `cargo build --release` → `rust/libentangle_rust.so` | 首次编译 2–10 分钟（发热正常） |
| 5 | **MicroPython** | `micropython/check_beacon_mp.py`（真解释器） | `MicroPython 真解释器自检: 全部 PASS ✓` |
| 6 | **Verilog** | `iverilog` 仿真 `tb_entangle.v` | `RTL 验证: 全部 PASS ✓` |
| 7 | **Python** | `test_host.py` 信标逻辑仿真 | `MicroPython 信标仿真: 全部 PASS ✓` |

> Rust 首次编译内存吃紧时（报 OOM/被系统杀）：
> ```bash
> export CARGO_BUILD_JOBS=1
> export RUSTFLAGS="-C opt-level=1"
> cargo build --release
> ```
> 并把手机插电、关闭后台 App。

---

## 5. 运行操作流程

### 5.1 单轮：真实纠缠 + 34m 信号波

```bash
cd ~/34/lang7
python3 python/orchestrator.py ../entangled.pdf ../sample2.pdf
```

预期（7 阶段全部 `PASS`；数值为示例，随输入文件略有变化）：
```
[1] C/C++ 引擎（libeng.so）
  [PASS] 纠缠完成 浓度≥34%  — conc=46.71% n=289817 θ=1.5708 R=8
  [PASS] 深度趋于 99.99%  — netDepth=99.99% raw=96.57% sel=94.89%
[2] Rust 纠缠数学模块
  [PASS] 浓度独立复算与 C 一致  — rust=0.464296 c=0.464296
  [PASS] EPR 密钥派生一致  — K[0]=0x89
[3] 汇编内核
  [PASS] pairmix 汇编 == C 参考  — asm=... c=...
[4] Python 编排 · 34m 信号波（UDP 组播 224.0.0.34:34034, TTL=2）
  [PASS] 信标发射→接收 4 帧  — rx=4 crc16 全过=True
  [PASS] 联合测量  — 33/33 位一致
[5] MicroPython … [PASS]
[6] Verilog … [PASS]
  七语言协同 · 结果汇总: 全部 PASS ✓
```

### 5.2 持续巡回长跑（核心实验）

```bash
bash tour_phone.sh            # 无限运行，Ctrl-C 优雅停止并出审计报告
bash tour_phone.sh 3600       # 运行 1 小时后自动停止
TOUR_RANDOM_SEED=1 bash tour_phone.sh   # 每轮轮转数据种子（确定性序列）
```

运行时每轮输出（养成阶段 growth→sustain→mature）：
```
[轮  12 sustain] conc=46.43% net=99.9900% raw=97.77% sel=96.28% depthRounds=65536 R=8 | tx=.. rx=.. crcBad=0 joint=.. /.. | 2.0s
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--period` | 5 s | 轮间间隔 |
| `--beacon-period` | 2 s | 持续发射信标间隔（与轮次解耦） |
| `--depth-rounds` | 64 | 养成起点，每轮 ×2 → 65536 |
| `--random-seed` | off | 种子轮转（CHSH 测量始终随机化） |
| `--fault-inject` | 空 | `engine@2,beacon_tx@3` 注入故障演示自愈 |
| `--log / --curve` | tour_log.jsonl / tour_curve.jsonl | 全量日志 / 养成曲线 |

**养成模型**：每轮 depthRounds ×2，净深度恒 ≥ 99.99%，同时
rawDepth 0.818→0.978、selFrac 0.575→0.963 单调增长；连续 5 轮达标 → 成熟。

**自愈演示**：
```bash
python3 python/tour.py ../entangled.pdf ../sample2.pdf --emit \
    --fault-inject "engine@2,beacon_tx@3" --max-rounds 5
```
预期：第 2 轮引擎路径故障 → L1 注入 → L2 切换真实输入自愈；第 3 轮信标 socket
被关 → L3 重建自愈；故障轮次照常 `PASS`。

### 5.3 34 米范围实测（第二台设备）

1. 发射端：vivo X300 保持 `tour_phone.sh` 运行（或至少跑过单轮）；
2. 接收端：**同一 WiFi** 下的第二台设备（电脑 / 另一部 Termux 手机）：
```bash
cd ~/34/lang7    # 第二台设备同样要有代码
python3 python/beacon_rx.py --a ../entangled.pdf --b ../sample2.pdf
```
3. 从发射机走开到 **34 m**，观察接收端持续打印帧（带 CRC OK 与 seed/θ/R 元数据），
   每帧还独立重建 EPR 共享并核对（效度验证）。

> 诚实披露：
> * 范围 34 m 是设计目标，实际受 AP 功率/天线/遮挡影响，请记录实测距离与成功率；
> * Android 接收组播需屏幕常亮（多播锁）；收不到时先用电脑试；
> * 路由器开启 **AP 隔离** 会挡组播，需关闭；
> * 这是经典电磁波（WiFi），不是量子传输。

### 5.4 查看实验结果

```bash
# 养成曲线（每轮 raw/sel/net/conc/depthRounds）
cat tour_curve.jsonl
# 全量日志（含十项指标 + 自愈事件 + CLASSICAL-SIM 伦理标记）
cat tour_log.jsonl
# 停止巡回后自动打印十项属性审计报告
```

---

## 6. 十项科学属性（操作者核对清单）

停止巡回（Ctrl-C）后自动输出审计；对照清单核验：

| 属性 | 看哪里 | 达标标准 |
|---|---|---|
| 可重复性 | 系统校验行 | 同 seed 重跑 → 逐字节一致（Δ=0） |
| 可控制性 | 审计行 | 12/12 参数经 CLI 可控 |
| 可测量性 | 审计行 | 14/14 指标数值化落日志 |
| 随机化 | 审计行 | CHSH 设置逐对随机（种子固定可复现） |
| 可证伪性 | 系统校验 + 审计 | 全零输入被拒（conc=0）；CHSH S ≤ 2 |
| 客观性 | 系统校验 | C / Rust / Python 三路 Δ < 1e-9 |
| 信度 | 系统校验 | K[0]=0x89、CRC=0x29B1 跨语言 golden |
| 效度 | 审计行 | 联合测量 100% 还原 A⊕B；单边熵≈8 |
| 伦理性 | 日志 | 每行含 CLASSICAL-SIM 标记，无伪量子宣称 |
| 透明性 | 日志/源码 | JSONL 全量 + 量化误差 0.0027pp 已披露 |

**深度趋于 99.99%**：每轮 `netDepth=99.9900%`；养成曲线展示 raw/sel 单调趋近。

---

## 7. 常见问题（FAQ）

**Q1 `pkg` 下载慢/失败**
换清华源（见 1.2），或换个时段重试；`pkg upgrade` 首次下载约 1GB。

**Q2 Rust 编译被杀 / 内存不足**
```bash
export CARGO_BUILD_JOBS=1
export RUSTFLAGS="-C opt-level=1"
cd rust && cargo build --release
```
插电、关闭后台 App；天玑9500 编译发热属正常。

**Q3 汇编差分测试找不到 `ec_pairmix_asm`**
确认 `build/pairmix.o` 存在（`ls -la build/`）；AArch64 版是
`asm/pairmix_aarch64.S`（build_phone.sh 已自动选择）。

**Q4 iverilog 找不到**
`pkg install -y iverilog`；安装后 `make sim` 会真跑 RTL 仿真。

**Q5 第二台设备收不到信标**
按 5.3 的披露逐项排查：同一 WiFi、屏幕常亮、关 AP 隔离、先电脑后手机。

**Q6 Termux 运行中被打断**
手机省电策略会杀后台：`termux-wake-lock` + 系统设置里把 Termux 加入电池白名单
（设置→应用→Termux→电池→不限制）。

**Q7 换用别的 PDF 做实验**
任意两个文件即可（不限于 PDF）：
```bash
python3 python/tour.py 我的文件A.pdf 我的文件B.pdf --emit
```
若浓度不足 34%，引擎会自动补轮次；仍不足则报错（可证伪性：不硬凑）。

---

## 8. 目录与产物

```
~/34/lang7/
├── install_phone.sh      # 一键安装（本节脚本）
├── build_phone.sh        # 手机构建（AArch64 NEON + Rust + iverilog）
├── tour_phone.sh         # 巡回长跑入口
├── Makefile              # 沙盒/通用构建
├── c_cpp/                # C 核心 + C++ 引擎
├── rust/                 # Rust 模块（cdylib FFI + CLI + 单测）
├── asm/                  # AArch64 NEON / x86-64 SSE2 汇编 + 差分测试
├── python/               # orchestrator.py / tour.py / cultivation.py /
│                         # selfheal.py / audit.py / beacon_rx.py / rust_twin.py
├── micropython/          # beacon 固件 + test_host.py + check_beacon_mp.py
├── verilog/              # 纠缠门/PRF/CRC/调制 RTL + golden 向量
├── tour_log.jsonl        # 巡回全量日志（运行时生成）
└── tour_curve.jsonl      # 养成曲线（运行时生成）
```
