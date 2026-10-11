/* r0=PCM16指针，r1=样本数0..65535，返回r0=绝对值和。 */
.syntax unified
.arm
.text
.global pcm_sum_abs_arm
.type pcm_sum_abs_arm, %function
pcm_sum_abs_arm:
    mov r2, #0
    cmp r1, #0
    beq sum_done
sum_loop:
    ldrsh r3, [r0], #2
    cmp r3, #0
    rsblt r3, r3, #0
    add r2, r2, r3
    subs r1, r1, #1
    bne sum_loop
sum_done:
    mov r0, r2
    bx lr
.size pcm_sum_abs_arm, .-pcm_sum_abs_arm

/* r0=绝对值和，r1=样本数，r2=门限0..32768；空帧返回0。 */
.global pcm_gate_arm
.type pcm_gate_arm, %function
pcm_gate_arm:
    cmp r1, #0
    moveq r0, #0
    bxeq lr
    mul r3, r1, r2
    cmp r0, r3
    movhs r0, #1
    movlo r0, #0
    bx lr
.size pcm_gate_arm, .-pcm_gate_arm
.section .note.GNU-stack,"",%progbits
