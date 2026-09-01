/* ============================================================================
 * tb_entangle.v — 七语言协同 · RTL 测试台 (lang7)
 *
 * 运行（需 iverilog）：
 *   make sim
 * 检查项（golden 由 sim_twin.py 依据 C/Python 数学生成，写入 golden.mem）：
 *   1) epr_prf：K[0..7] 与 C 核心 golden 逐字节一致
 *   2) crc16："123456789" → 0x29B1（与 C/Rust/MicroPython 一致）
 *   3) entangle_gate：多组 (x,y) 的 p_q 与 golden 一致
 *   4) beacon_mod：前导/停止位与总位周期正确
 * 任一失败 $finish(1)；全部通过 $finish(0)。
 * ========================================================================== */
`timescale 1ns/1ps
module tb_entangle;
    reg clk = 0;
    always #5 clk = ~clk;   // 100 MHz

    // ---------- 1) epr_prf ----------
    reg rst_n = 0, next_r = 0;
    reg [63:0] seed = 64'd34;
    wire [7:0] k_out;
    wire k_valid;
    epr_prf u_prf (.clk(clk), .rst_n(rst_n), .next_r(next_r),
                   .seed(seed), .key_out(k_out), .valid(k_valid));

    integer prf_fail = 0;
    integer prf_i;
    reg [7:0] golden_key [0:7];
    initial begin
        $readmemh("golden_key.mem", golden_key);
        @(negedge rst_n);
        @(posedge clk);
        for (prf_i = 0; prf_i < 8; prf_i = prf_i + 1) begin
            next_r = 1;
            @(posedge clk);
            next_r = 0;
            @(posedge clk);
            if (k_out !== golden_key[prf_i]) begin
                $display("[FAIL] epr_prf K[%0d] = %02h expect %02h",
                         prf_i, k_out, golden_key[prf_i]);
                prf_fail = 1;
            end
        end
        if (!prf_fail)
            $display("[PASS] epr_prf K[0..7] 与 C 核心 golden 一致");
    end

    // ---------- 2) crc16 ----------
    reg [7:0] c_byte = 0;
    reg c_valid = 0, c_init = 0;
    wire [15:0] crc_out;
    crc16 u_crc (.clk(clk), .rst_n(rst_n), .byte_in(c_byte),
                 .byte_valid(c_valid), .init(c_init), .crc_out(crc_out));
    reg crc_fail = 0;
    integer ci;
    initial begin
        @(negedge rst_n);
        @(posedge clk);
        c_init = 1;
        @(posedge clk);
        c_init = 0;
        for (ci = 0; ci < 9; ci = ci + 1) begin
            case (ci)
                0: c_byte = "1"; 1: c_byte = "2"; 2: c_byte = "3";
                3: c_byte = "4"; 4: c_byte = "5"; 5: c_byte = "6";
                6: c_byte = "7"; 7: c_byte = "8"; 8: c_byte = "9";
            endcase
            c_valid = 1;
            @(posedge clk);
            c_valid = 0;
            @(posedge clk);
        end
        if (crc_out === 16'h29B1)
            $display("[PASS] crc16(\"123456789\") = 29B1 与 C/Rust/MicroPython 一致");
        else begin
            $display("[FAIL] crc16 = %04h expect 29B1", crc_out);
            crc_fail = 1;
        end
    end

    // ---------- 3) entangle_gate ----------
    reg [7:0] gx = 0, gy = 0;
    wire [15:0] p_q;
    entangle_gate u_gate (.x(gx), .y(gy), .p_q(p_q));
    reg gate_fail = 0;
    integer gi;
    reg [15:0] golden_p [0:7];
    initial begin
        $readmemh("golden_p.mem", golden_p);
        @(negedge rst_n);
        @(posedge clk);
        for (gi = 0; gi < 8; gi = gi + 1) begin
            case (gi)
                0: begin gx = 8'd10; gy = 8'd10; end
                1: begin gx = 8'd34; gy = 8'd34; end
                2: begin gx = 8'd0;  gy = 8'd255; end
                3: begin gx = 8'd128; gy = 8'd128; end
                4: begin gx = 8'd255; gy = 8'd0; end
                5: begin gx = 8'd77;  gy = 8'd199; end
                6: begin gx = 8'd200; gy = 8'd100; end
                7: begin gx = 8'd34;  gy = 8'd99; end
            endcase
            #1;
            if (p_q !== golden_p[gi]) begin
                $display("[FAIL] gate(x=%0d,y=%0d) p=%05d expect %05d",
                         gx, gy, p_q, golden_p[gi]);
                gate_fail = 1;
            end
        end
        if (!gate_fail)
            $display("[PASS] entangle_gate 8 组 (x,y) 与 C/Python golden 一致");
    end

    // ---------- 4) beacon_mod ----------
    reg [7:0] f_byte = 0;
    reg f_valid = 0, f_end = 0;
    wire b_tx, b_busy;
    beacon_mod #(.BIT_TICKS(2)) u_mod (.clk(clk), .rst_n(rst_n),
        .frame_byte(f_byte), .byte_valid(f_valid), .frame_end(f_end),
        .tx(b_tx), .busy(b_busy));
    reg mod_fail = 0;
    initial begin
        @(negedge rst_n);
        @(posedge clk);
        f_byte = 8'h34;
        f_valid = 1;
        @(posedge clk);
        f_valid = 0;
        f_end = 1;
        // 等完成：16 前导 + 8 数据 + 1 停止 = 25 bit × 2 ticks
        repeat (25 * 2 + 2) @(posedge clk);
        if (b_busy !== 1'b0) begin
            $display("[FAIL] beacon_mod 未在期望周期内完成");
            mod_fail = 1;
        end else begin
            $display("[PASS] beacon_mod 前导16+数据8+停止1 位周期正确");
        end
    end

    // ---------- 汇总 ----------
    initial begin
        rst_n = 0;
        #40 rst_n = 1;
        #20000;
        if (prf_fail || crc_fail || gate_fail || mod_fail) begin
            $display("RTL 验证: FAIL ✗");
            $finish(1);
        end else begin
            $display("RTL 验证: 全部 PASS ✓");
            $finish(0);
        end
    end
endmodule
