/* ============================================================================
 * pairmix_aarch64.S — 七语言协同 · ARM64 (AArch64) 汇编内核 (lang7)
 *
 * uint64_t ec_pairmix_asm(const uint8_t* pa, const uint8_t* pb, size_t n);
 *   计算 Σ |pa[i] − pb[i]|（秩配对后的字节差之和，配对质量度量）。
 *
 *   目标设备：vivo X300 · 天玑9500（ARMv9 / AArch64，Cortex-X925 + A725）。
 *   用 NEON (ASIMD) 向量化：一次 16 对，|a−b| 用 UABD + UADDLV 纵向累加。
 *
 * 调用约定 (AAPCS64): x0=pa, x1=pb, x2=n, 返回 x0。
 * ========================================================================== */

#if defined(__aarch64__)
    .text
    .p2align 4
    .globl  ec_pairmix_asm
    .type   ec_pairmix_asm, %function
ec_pairmix_asm:
    mov     x3, #0                  // 标量累加和
    movi    v2.2d, #0               // 向量累加和（2×64bit 车道）
    lsr     x4, x2, #4              // 16 字节块数
    cbz     x4, .Ltail_a64

    .p2align 4
.Lvec_a64:
    ld1     {v0.16b}, [x0], #16     // pa[0..15]
    ld1     {v1.16b}, [x1], #16     // pb[0..15]
    uabd    v0.16b, v0.16b, v1.16b  // 无符号绝对差（16×8bit）
    uaddlv  d0, v0.16b              // 纵向求和 → 64 位
    add     v2.2d, v2.2d, v0.2d     // 累加（d0 高车道为 0）
    subs    x4, x4, #1
    b.ne    .Lvec_a64

    addp    v2.2d, v2.2d, v2.2d     // 两车道相加
    umov    x5, v2.d[0]
    add     x3, x3, x5

.Ltail_a64:
    and     x4, x2, #15             // 剩余 0..15 字节
    cbz     x4, .Ldone_a64
    mov     x5, #0
.Ltail_loop_a64:
    ldrb    w6, [x0, x5]
    ldrb    w7, [x1, x5]
    subs    w6, w6, w7
    cneg    w6, w6, mi              // |a−b|
    add     x3, x3, x6
    add     x5, x5, #1
    cmp     x5, x4
    b.lt    .Ltail_loop_a64

.Ldone_a64:
    mov     x0, x3
    ret
    .size   ec_pairmix_asm, .-ec_pairmix_asm
    .section .note.GNU-stack,"",@progbits
#endif
