/* ============================================================================
 * epr_prf.v — 七语言协同 · EPR 密钥派生 PRF (lang7)
 *
 * splitmix64 PRF 的 RTL 实现，产生 8-bit 密钥流 K[r]：
 *   x = seed ⊕ r·φ ;  x = splitmix64(x) ;  K[r] = x[63:56]
 * 与 C 核心 ec_key_byte / Rust key_byte / Python / MicroPython 同算法。
 * 每拍输出一个密钥字节（组合 mix 链 + 寄存器，可综合）。
 * ========================================================================== */
module epr_prf (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        next_r,     // 拉高一拍：派生下一个 K[r]
    input  wire [63:0] seed,
    output reg  [7:0]  key_out,    // K[r]
    output reg         valid
);
    localparam [63:0] PHI = 64'h9E3779B97F4A7C15;
    localparam [63:0] M1  = 64'hBF58476D1CE4E5B9;
    localparam [63:0] M2  = 64'h94D049BB133111EB;

    reg [63:0] r;

    // splitmix64 组合实现
    function [63:0] splitmix64;
        input [63:0] x0;
        reg [63:0] x;
        begin
            x = x0 + PHI;
            x = (x ^ (x >> 30)) * M1;
            x = (x ^ (x >> 27)) * M2;
            splitmix64 = x ^ (x >> 31);
        end
    endfunction

    wire [63:0] x_in  = seed ^ (r * PHI);
    wire [63:0] x_mix = splitmix64(x_in);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r      <= 64'd0;
            key_out <= 8'd0;
            valid  <= 1'b0;
        end else if (next_r) begin
            r       <= r + 1'b1;
            key_out <= x_mix[63:56];   // K[r] = 高 8 位
            valid   <= 1'b1;
        end else begin
            valid <= 1'b0;
        end
    end
endmodule
