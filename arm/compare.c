#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <time.h>

extern uint32_t pcm_sum_abs_arm(const int16_t *, uint32_t);
extern uint32_t pcm_gate_arm(uint32_t, uint32_t, uint32_t);
extern uint32_t pcm_sum_abs_c(const int16_t *, uint32_t);
static double seconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
int main(void) {
    int16_t normal[] = {1000, -1000, 1000, -1000};
    int16_t below[] = {499, -499, 499, -499};
    int16_t equal[] = {500, -500, 500, -500};
    int16_t edge[] = {-32768, 32767, 0, -1};
    int16_t *cases[] = {normal, below, equal, edge, normal};
    const char *names[] = {"normal", "below", "equal", "pcm_boundary", "empty"};
    uint32_t lengths[] = {4, 4, 4, 4, 0};
    uint32_t i, j;
    volatile uint32_t checksum = 0;
    int failed = 0;
    printf("case,c_sum,arm_sum,c_gate,arm_gate,c_seconds,arm_seconds\n");
    for (i = 0; i < 5; ++i) {
        uint32_t n = lengths[i], c = pcm_sum_abs_c(cases[i], n);
        uint32_t a = pcm_sum_abs_arm(cases[i], n);
        uint32_t cg = n && c >= n * 500, ag = pcm_gate_arm(a, n, 500);
        double start = seconds(), ct, at;
        for (j = 0; j < 100000; ++j) checksum ^= pcm_sum_abs_c(cases[i], n);
        ct = seconds() - start;
        start = seconds();
        for (j = 0; j < 100000; ++j) checksum ^= pcm_sum_abs_arm(cases[i], n);
        at = seconds() - start;
        printf("%s,%u,%u,%u,%u,%.9f,%.9f\n", names[i], c, a, cg, ag, ct, at);
        failed |= c != a || cg != ag;
    }
    (void)checksum;
    /* 此微基准含调用和循环开销，不代表整条语音链路延迟。 */
    return failed ? 1 : 0;
}
