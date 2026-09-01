/* ============================================================================
 * pairmix_x86_64.S — 七语言协同 · x86-64 汇编内核 (lang7)
 *
 * uint64_t ec_pairmix_asm(const uint8_t* pa, const uint8_t* pb, size_t n);
 *   计算 Σ |pa[i] − pb[i]|（秩配对后的字节差之和，配对质量度量）。
 *   目标设备 vivo X300 是天玑9500 (ARM64)，这是本地测试/交叉验证用的 x86-64 版；
 *   ARM64 版见 pairmix_aarch64.S，二者接口与结果完全一致。
 *
 * 寄存器:  rdi=pa, rsi=pb, rdx=n, rax=累加和（无符号）
 * 采用 SSE2 向量化：一次处理 16 对（psadbw 差绝对值和）。
 * ========================================================================== */

#if defined(__x86_64__)
    .text
    .p2align 4
    .globl  ec_pairmix_asm
    .type   ec_pairmix_asm, @function
ec_pairmix_asm:
    xorl    %eax, %eax          # 标量累加和 = 0
    xorps   %xmm3, %xmm3        # 向量累加和 = 0
    movq    %rdx, %rcx
    shrq    $5, %rcx            # 32 字节块数（每轮 2×16B）
    jz      .Ltail

    .p2align 4
.Lvec:
    movdqu  (%rdi), %xmm0       # pa[0..15]
    movdqu  (%rsi), %xmm1       # pb[0..15]
    movdqu  16(%rdi), %xmm2     # pa[16..31]
    psadbw  %xmm1, %xmm0        # |差| 每 8 字节一组的和 → xmm0[0],xmm0[8]
    movdqu  16(%rsi), %xmm1     # pb[16..31]
    psadbw  %xmm1, %xmm2
    paddq   %xmm0, %xmm3
    paddq   %xmm2, %xmm3
    addq    $32, %rdi
    addq    $32, %rsi
    decq    %rcx
    jnz     .Lvec

    movdqa  %xmm3, %xmm0
    psrldq  $8, %xmm0
    paddq   %xmm3, %xmm0
    movq    %xmm0, %rax         # 向量部分和

.Ltail:
    andq    $31, %rdx           # 剩余 0..31 字节
    jz      .Ldone
    xorl    %ecx, %ecx
.Ltail_loop:
    movzbl  (%rdi,%rcx), %r8d
    movzbl  (%rsi,%rcx), %r9d
    subl    %r9d, %r8d          # r8d = x − y ∈ [−255,255]
    movl    %r8d, %r10d
    sarl    $31, %r10d          # 符号掩码：全 1（负）或全 0（正）
    movl    %r8d, %r9d
    xorl    %r10d, %r9d
    subl    %r10d, %r9d         # branchless abs：|x−y|
    addq    %r9, %rax
    incq    %rcx
    cmpq    %rdx, %rcx
    jb      .Ltail_loop
.Ldone:
    ret
    .size   ec_pairmix_asm, .-ec_pairmix_asm
    .section .note.GNU-stack,"",@progbits
#endif
