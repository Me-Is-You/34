/* ============================================================================
 * beacon_mod.v — 七语言协同 · 34m 信标 OOK 调制器 RTL (lang7)
 *
 * 串行化 + OOK 调制：
 *   前导码 0xAA 0xAA（16 bit，LSB 先）→ 帧字节（每字节 8 bit，LSB 先）
 *   → 停止位 '1' → 回到空闲
 *   每位持续 BIT_TICKS 个时钟；tx 输出直接驱动 433MHz 发射管脚 / LED。
 * 由上位机（MicroPython/ESP32 或 vivo X300）提供帧字节流。
 * ========================================================================== */
module beacon_mod #(
    parameter BIT_TICKS = 8,
    parameter PREAMBLE  = 32'hAAAAAAAA   // 16 bit 前导 ×2（低 16 位先发）
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  frame_byte,
    input  wire        byte_valid,   // 写入一字节
    input  wire        frame_end,    // 最后一字节后拉高一拍
    output reg         tx,           // OOK 输出
    output reg         busy
);
    localparam TOTAL_BITS = 16 + 8 + 1;          // 前导 16 + 数据 8 + 停止 1

    reg [4:0]  bit_pos;      // 0..24
    reg [2:0]  tick;
    reg [7:0]  shifter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx      <= 1'b0;
            busy    <= 1'b0;
            bit_pos <= 5'd0;
            tick    <= 3'd0;
            shifter <= 8'h00;
        end else if (!busy) begin
            if (byte_valid) begin
                busy    <= 1'b1;
                bit_pos <= 5'd0;
                tick    <= 3'd0;
                shifter <= frame_byte;
            end
        end else begin
            if (tick == BIT_TICKS - 1) begin
                tick <= 3'd0;
                if (bit_pos < 5'd16) begin
                    tx <= PREAMBLE[bit_pos];     // 前导位（LSB 先）
                    bit_pos <= bit_pos + 1'b1;
                end else if (bit_pos == 5'd16) begin
                    tx <= shifter[0];
                    bit_pos <= bit_pos + 1'b1;
                end else if (bit_pos < 5'd24) begin
                    tx <= shifter[bit_pos - 5'd16];
                    bit_pos <= bit_pos + 1'b1;
                end else begin
                    tx <= 1'b1;                  // 停止位
                    bit_pos <= bit_pos + 1'b1;
                end
                if (bit_pos == TOTAL_BITS - 1) begin
                    busy <= 1'b0;                // 完成
                    if (frame_end) tx <= 1'b1;
                end
            end else begin
                tick <= tick + 1'b1;
            end
        end
    end
endmodule
