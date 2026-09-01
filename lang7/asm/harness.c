/* ============================================================================
 * harness.c — 七语言协同 · 汇编内核验证 (lang7)
 *
 * 用随机数据 + 真实 PDF 字节流，把汇编 ec_pairmix_asm 与 C 参考
 * ec_pairmix_c 逐位对照。任一失配即退出码 1（可证伪性）。
 * ========================================================================= */
#include "../c_cpp/entangle_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

extern uint64_t ec_pairmix_asm(const uint8_t* pa, const uint8_t* pb, size_t n);

static int test_round(const uint8_t* a, size_t na, const uint8_t* b, size_t nb,
                      const char* name) {
    size_t n = na > nb ? na : nb;
    uint32_t* pa = (uint32_t*)malloc(n * sizeof(uint32_t));
    uint32_t* pb = (uint32_t*)malloc(n * sizeof(uint32_t));
    if (!pa || !pb) { fprintf(stderr, "oom\n"); return 0; }
    ec_rank_pair(a, na, b, nb, pa, pb);
    uint8_t* xa = (uint8_t*)malloc(n);
    uint8_t* xb = (uint8_t*)malloc(n);
    for (size_t i = 0; i < n; ++i) {
        xa[i] = a[pa[i] % na];
        xb[i] = b[pb[i] % nb];
    }
    uint64_t asm_ = ec_pairmix_asm(xa, xb, n);
    uint64_t c_ = ec_pairmix_c(a, na, b, nb, pa, pb);
    int ok = (asm_ == c_);
    printf("[%s] n=%zu asm=%llu c=%llu %s\n", name, n,
           (unsigned long long)asm_, (unsigned long long)c_,
           ok ? "PASS" : "FAIL");
    free(pa); free(pb); free(xa); free(xb);
    return ok;
}

int main(int argc, char** argv) {
    int all = 1;
    /* 1) 边界：空 */
    {
        uint8_t z = 0;
        all &= test_round(&z, 0, &z, 0, "empty");
    }
    /* 2) 随机数据（多种长度，覆盖向量+尾部路径） */
    srand(34);
    for (int len = 1; len <= 100; ++len) {
        size_t n = (size_t)(rand() % 2000) + 1;
        uint8_t* a = (uint8_t*)malloc(n);
        uint8_t* b = (uint8_t*)malloc(n);
        for (size_t i = 0; i < n; ++i) { a[i] = (uint8_t)rand(); b[i] = (uint8_t)rand(); }
        char nm[64]; snprintf(nm, sizeof nm, "rand#%d", len);
        all &= test_round(a, n, b, n, nm);
        free(a); free(b);
    }
    /* 3) 真实 PDF 字节（若有） */
    if (argc >= 3) {
        FILE* fa = fopen(argv[1], "rb");
        FILE* fb = fopen(argv[2], "rb");
        if (fa && fb) {
            fseek(fa, 0, SEEK_END); fseek(fb, 0, SEEK_END);
            long la = ftell(fa), lb = ftell(fb);
            fseek(fa, 0, SEEK_SET); fseek(fb, 0, SEEK_SET);
            uint8_t* a = (uint8_t*)malloc(la ? la : 1);
            uint8_t* b = (uint8_t*)malloc(lb ? lb : 1);
            if (fread(a, 1, la, fa) != (size_t)la || fread(b, 1, lb, fb) != (size_t)lb) {
                fprintf(stderr, "read fail\n"); return 1;
            }
            all &= test_round(a, la, b, lb, "real-pdf");
            free(a); free(b);
        }
        if (fa) fclose(fa);
        if (fb) fclose(fb);
    }
    printf("汇编内核 vs C 参考: %s\n", all ? "全部一致 ✓" : "存在失配 ✗");
    return all ? 0 : 1;
}
