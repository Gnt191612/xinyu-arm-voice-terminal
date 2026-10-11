#include <stdint.h>

/* 单独编译且不启用LTO，避免编译器将重复调用提前算成常量。 */
uint32_t pcm_sum_abs_c(const int16_t *p, uint32_t n) {
    uint32_t sum = 0, i;
    for (i = 0; i < n; ++i) {
        int32_t value = p[i];
        sum += value < 0 ? -value : value;
    }
    return sum;
}
