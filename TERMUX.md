# Termux 实验指南（安卓手机）

> 零依赖、纯 C++17，手机照跑不误。全程约 3 分钟。

## 1. 安装环境（一次性）

```bash
pkg update -y
pkg install -y clang make git python
```

> 想读取手机存储里的 PDF？先授权一次：
> ```bash
> termux-setup-storage
> ```
> 之后手机上的文件都在 `~/storage/shared/`（如 `~/storage/shared/Download/`）。

也可以直接：
```bash
make termux-setup    # 等价于上面两条 pkg 命令
```

## 2. 获取代码并构建

```bash
git clone https://github.com/Me-Is-You/34.git
cd 34
make
```

Makefile 会自动检测编译器：Termux 用 **clang++**，桌面用 g++，都不用管。
构建产物 `entangle` 约 110 KB。

## 3. 快速自测（不需要任何输入文件）

```bash
make demo      # 纠缠「核心物理构想.pdf」× sample2.pdf
make verify    # 11 项真实性检验，应全部 PASS
```

手机上示例输出（0.8s 跑完 28 万对）：

```
纠缠浓度值          = 44.43%    ← ≥ 34% 阿雷纳常数：PASS ✓
提纯贝尔对          = 126801 / 285385
EPR 互信息 I(A';B') = 6.63 bit/字节
verify: 11/11 PASS
```

## 4. 用自己的 PDF 实验

```bash
# 把 PDF 放进手机 Download 目录，然后：
cp ~/storage/shared/Download/我的论文.pdf ./
cp ~/storage/shared/Download/我的笔记.pdf ./

./entangle entangle 我的论文.pdf 我的笔记.pdf -o out.pdf --fast --report r.txt
./entangle verify out.pdf out.pdf.shareA.bin out.pdf.shareB.bin
./entangle audit          # 十项科学属性审计（可选）
```

参数速查：

| 选项 | 说明 | 手机建议 |
|---|---|---|
| `--fast` | 快速模式（更少退火迭代、更小采样） | ✅ 推荐 |
| `--depth-rounds <R>` | 深度提纯轮数（净深度趋于 99.99%） | 默认 `16384`，关掉用 `0` |
| `--randomize-seed` | 每次真随机种子（随机化实验） | 想复现就关掉 |
| `--seed <n>` | 纠缠种子 | 默认 `34` |
| `--theta/--rounds` | 固定纠缠门角度/蒸馏轮数 | 想复现再固定 |
| `--min-conc <x>` | 浓度下限（低于 34% 自动提升） | 别改，阿雷纳常数守恒 |

## 4b. 持续运行巡回模式（养手机上的模型）

```bash
mkdir -p inbox out
./entangle tour --in inbox --out out --journal journal.log --model model.txt --poll 10
# 另一终端：把 PDF 丢进 inbox/
cp ~/storage/shared/Download/我的论文.pdf inbox/
cp ~/storage/shared/Download/我的笔记.pdf inbox/
# tour 会自动成对纠缠 → 自检 → 写入 out/ → 养成模型（Ctrl-C 优雅停止）
./entangle model    # 查看养成的先验
```

## 5. 查看结果

- **entangled.pdf**：在手机文件管理器里点开即可看报告页；
  附件（两份原始 PDF）可用支持附件的阅读器导出。
- **shareA.bin / shareB.bin**：二进制噪声，不要直接"打开"。
  想看内容用 `xxd shareA.bin | head`。

## 6. 常见问题

**Q：`make` 报 `g++: command not found`？**
A：不会——Makefile 已自动切换到 clang++。若仍报错，手动指定：
`make CXX=clang++`。

**Q：文件很大，手机扛得住吗？**
A：10 MB PDF ≈ 1000 万量子比特对，全量浓度计算约几百 MB 内存 + 几秒，
主流手机没问题。优化阶段只采样 16384 对，很快。真觉得慢就 `--fast`。

**Q：中文文件名乱码？**
A：Android 文件系统是 UTF-8，中文文件名直接可用。终端里输中文麻烦的话，
把文件改名成 `a.pdf` / `b.pdf` 即可，纠缠结果不受文件名影响。

**Q：手机上没有 C/C++ 基础？**
A：没关系——`make demo` 一行命令跑完，verify 全是 PASS 就是成功的信号。
波函数已坍缩，浓度值 44.43%，阿雷纳常数 34% 不可破。
