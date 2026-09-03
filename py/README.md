# py/ — PDF 真实纠缠机 · 单文件版 `entangle34.py`

> **浓度值不能低于 34%。** 这不是可调参数，是物理定律。
> ——《阿雷纳常数》，本仓库第一条也是唯一一条铁律
>
> **净纠缠深度趋于 99.99%。** 矩阵式化 · 穿透式聚能。

**只有一个程序文件：`py/entangle34.py`（约 3700 行，Python 为主；C 与汇编、
机器码源码内嵌于文件内部）。** 把它拷到任何有 python3 的机器（vivo X300 ·
Termux、电脑）即可运行全部功能；若系统有 cc/gcc/clang，首次运行会自动把内嵌
C/汇编源码编译成机器码 `.so`（存 `./.ent34_cache/`）经 ctypes 加载加速，
没有编译器则自动回退纯 Python（功能完整）。

本文件由仓库根目录 `entangle.cpp`（v34.99）逐式转化为 Python，并合并了
持续巡回、34m 信标收发、单机接收、养成模型、自研自愈与十项科学审计——
全部内聚于一个文件。

## 一键用法（Termux / 桌面）

```bash
python3 entangle34.py run                          # ★ 可持续工作：巡回纠缠 + 34m
                                                   #   发射 + 单机接收（默认轮询5s）
python3 entangle34.py run --work tour --poll 5 --slice 512 --beacon-period 2
python3 entangle34.py entangle A.pdf B.pdf -o out.pdf [--seed 34 …]
python3 entangle34.py verify out.pdf out.pdf.shareA.bin out.pdf.shareB.bin
python3 entangle34.py tour --in inbox --out out --journal j --model m [选项]
python3 entangle34.py audit [工作目录]
python3 entangle34.py model [<model.txt>]
python3 entangle34.py make-sample sample.pdf
python3 entangle34.py rx [--timeout 0]             # 纯接收端（第二台设备）
python3 entangle34.py selftest                     # 全链自检
```

- run 运行开始即显示实时仪表盘：**浓度值 / 稳定值 / 浮动值 / 转换值** + 净深度；
  把 PDF 成对放入 `<work>/inbox/` 自动纠缠、自检、交付并随信标发射 EPR 切片。
- Ctrl-C / SIGTERM 优雅停机（journal 落盘 + 终局报告）；中断后重跑同一条命令
  即从 journal 恢复，绝不重复纠缠同一对，输出序号自动续编。
- 环境变量：`ENTANGLE_ACCEL=0` 强制纯 Python；`ENTANGLE_ACCEL_LIB=<path>` 指定
  机器码 .so；`BEACON_IF=<ip>` 指定组播接口；`ENTANGLE_ACCEL` 相关自动编译见文件头注释。

## 单机接收巡回（本版重点）

一个程序内同时运行：
- **发射线程**：心跳周期 + 每轮密集，UDP 组播 `224.0.0.34:34034`，TTL=2
  （≈802.11 一跳 30–50 m，34 m 为设计目标；启动即发引导帧，等待输入也不断流）；
- **接收线程**：同一进程全时监听组播、逐帧 CRC 校验，统计 rx_ok / rx_bad /
  丢帧 / 回环延迟 / 滑窗转换值 —— 单机自发自收即"单机接收巡回"；仪表盘与
  终局报告实时披露接收侧全部计数。
- `rx` 子命令 = 纯接收端（第二台设备收同一 WiFi 的 34m 信标，逐帧显示发射端
  浓度/净深度等实时四项）。

帧格式与 `lang7/` 的 C/Rust/Verilog/MicroPython 信标**逐字节一致**
（CRC-16/CCITT-FALSE golden `0x29B1`），指标尾块为本版扩展（旧解析器兼容忽略）。

## 与 C++ 版（根目录 entangle.cpp）的等价性

| 验证 | 方法 | 结果 |
|---|---|---|
| 数学逐位一致 | 同参数同 seed | conc/netDepth/raw/sel 与 C++ 逐位相同 |
| 产物字节一致 | 固定 θ=1.5708、R=7 纠缠同一对文件 | `entangled.pdf` **289747 字节全同** |
| 双向 verify | Python ⇄ C++ 互相验证对方产物 | 12/12 PASS（两方向） |
| make-sample | 本文件生成器 ⇄ C++ 生成器 | sample2.pdf 字节全同 |
| 全链自检 | `python3 entangle34.py selftest` | 26 PASS / 0 FAIL（含十项审计 10/10；纯 Python 模式 25/25） |
| 机器码辅助 | 内嵌 C/汇编自动编译 → ctypes | precompute/conc/depth 逐位一致 + 汇编差分一致 |

> 诚实披露：模拟退火的随机数流改用确定性 splitmix64 + Box–Muller（C++ 为
> libstdc++ mt19937_64），同 seed 完全可复现、硬约束全程不违反，轨迹不与 C++
> 逐位比较；无 C 加速时退火预算自动降为 150 迭代（`--iter 800` 可恢复全量）。

## 科学属性（十项，全部真实可运行）

可重复性（同 seed 字节一致）· 可控制性（θ/R CLI 精确生效）· 可测量性
（指标全部有限数值）· 随机化（真随机种子可选）· 可证伪性（全零被拒、
篡改被识破、CHSH ≤ 2 不作假）· 客观性（verify 仅凭产物重算）· 信度（重测一致）
· 效度（净深度 ≥99.99% + 浓度/并发度强相关）· 伦理性（输入零改动、如实披露）
· 透明性（journal/模型/曲线全量落盘）。

术语如实披露：本程序是经典信道对量子通道的模拟（共享密钥 = 局域隐变量），
"矩阵式化"= 每轮 1×N 指标行全量落盘，"穿透式聚能"= 退火/蒸馏把可纠缠权重向
高并发度子集集中；均为工程描述，不声称真实量子传输。
