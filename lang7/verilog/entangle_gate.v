/* ============================================================================
 * entangle_gate.v — 七语言协同 · 纠缠门 RTL (lang7)
 *
 * 布洛赫球映射 + 最大纠缠门 U(π/2) + Procrustean 浓缩的硬件实现。
 *
 * 数学（与 C/Rust/Python 同源，θ = π/2 化简，字节 x∈[0,255]）：
 *   φ(x) = π·x/510 ∈ [0, π/2]        （x=255 恰为 π/2）
 *   sinφ(x) 查表 = sine[ x ]
 *   cosφ(x) 查表 = sine[ 255 − x ]    （精确：sin(π/2 − φ) = sin(π·(255−x)/510)）
 *   C = 4·(cosφa·cosφb)·(sinφa·sinφb)   （C×2^15 = prod[58:43]，prod 为 2^60 定点）
 *   p = 1 − √(1 − C²)，C 量化 10 位查 1024×16 p ROM
 *
 * 表文件 sine.mem / p_rom.mem 由 `make sim` 先运行 sim_twin.py 生成；
 * sim_twin.py 同时核对 RTL 定点路径与 C 核心双精度数学的浓度偏差 < 0.5pp。
 * ========================================================================== */
module entangle_gate (
    input  wire [7:0]  x,          // 字节 A
    input  wire [7:0]  y,          // 字节 B
    output wire [15:0] p_q         // 单轮浓缩成功概率 p×65535
);

    reg [15:0] sin_lut [0:255];
    reg [15:0] p_rom   [0:1023];

    initial begin
        $readmemh("sine.mem", sin_lut);
        $readmemh("p_rom.mem", p_rom);
    end

    // 查表（定点 15 位小数，无符号，值域 [0,2^15]）
    wire [15:0] sfa = sin_lut[x];
    wire [15:0] cfa = sin_lut[8'd255 - x];
    wire [15:0] sfb = sin_lut[y];
    wire [15:0] cfb = sin_lut[8'd255 - y];

    // C = 4·(cfa·cfb)·(sfa·sfb)；prod 缩 2^60，prod[58:43] = C×2^15
    wire [31:0] t1 = cfa * cfb;
    wire [31:0] t2 = sfa * sfb;
    wire [63:0] prod = t1 * t2;
    wire [15:0] c_q = prod[58:43];

    // C 量化 10 位（clamp C=1 → 索引 1023）
    wire [15:0] c_c = (c_q == 16'h8000) ? 16'h7FFF : c_q;
    wire [9:0]  c_idx = c_c[15:5];

    assign p_q = p_rom[c_idx];

endmodule
