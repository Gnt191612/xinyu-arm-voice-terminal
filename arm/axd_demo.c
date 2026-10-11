#include <stdio.h>

extern unsigned int pcm_sum_abs_arm(const short *, unsigned int);
extern unsigned int pcm_gate_arm(unsigned int, unsigned int, unsigned int);

int main(void) {
    static short normal[] = {1000, -1000, 1000, -1000};
    static short below[] = {499, -499, 499, -499};
    static short equal[] = {500, -500, 500, -500};
    static short edge[] = {-32768, 32767, 0, -1};
    short *data[] = {normal, below, equal, edge, normal};
    unsigned int lengths[] = {4, 4, 4, 4, 0};
    unsigned int expected[] = {4000, 1996, 2000, 65536, 0};
    unsigned int expected_gate[] = {1, 0, 1, 1, 0};
    const char *names[] = {"normal", "below", "equal", "pcm_boundary", "empty"};
    unsigned int i, total, active;
    for (i = 0; i < 5; ++i) {
        total = pcm_sum_abs_arm(data[i], lengths[i]);
        active = pcm_gate_arm(total, lengths[i], 500);
        printf("%s sum=%u gate=%u %s\n", names[i], total, active,
               total == expected[i] && active == expected_gate[i] ? "PASS" : "FAIL");
        if (total != expected[i] || active != expected_gate[i]) return 1;
    }
    return 0;
}
