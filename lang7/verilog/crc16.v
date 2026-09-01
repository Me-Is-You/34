/* ============================================================================
 * crc16.v — 七语言协同 · CRC-16/CCITT-FALSE (lang7)
 *
 * 34 米信号波帧的完整性校验。逐字节输入：
 *   c = crc ^ byte<<8; 8× { c = (c&0x8000) ? (c<<1)^0x1021 : c<<1 }
 * 与 C 核心 ec_crc16 / Rust crc16 / MicroPython crc16 一致。
 * ========================================================================== */
module crc16 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  byte_in,
    input  wire        byte_valid,   // 每字节拉高一拍
    input  wire        init,         // 初始化 crc = 0xFFFF
    output wire [15:0] crc_out
);
    function [15:0] crc8;
        input [15:0] c0;
        input [7:0]  b;
        reg [15:0] c;
        integer i;
        begin
            c = c0 ^ ({b, 8'h00});
            for (i = 0; i < 8; i = i + 1)
                c = (c[15]) ? ((c << 1) ^ 16'h1021) : (c << 1);
            crc8 = c;
        end
    endfunction

    reg [15:0] crc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            crc <= 16'hFFFF;
        end else if (init) begin
            crc <= 16'hFFFF;
        end else if (byte_valid) begin
            crc <= crc8(crc, byte_in);
        end
    end

    assign crc_out = crc;
endmodule
