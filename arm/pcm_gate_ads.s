        AREA pcm_code, CODE, READONLY
        CODE32
        EXPORT pcm_sum_abs_arm
        EXPORT pcm_gate_arm
; 与GNU版本采用相同的A32指令，供课堂ARM7指令执行验证。
; 调用方保证样本数0..65535，门限0..32768，指针对齐且有效。
pcm_sum_abs_arm
        MOV r2, #0
        CMP r1, #0
        BEQ sum_done
sum_loop
        LDRSH r3, [r0], #2
        CMP r3, #0
        RSBLT r3, r3, #0
        ADD r2, r2, r3
        SUBS r1, r1, #1
        BNE sum_loop
sum_done
        MOV r0, r2
        BX lr
pcm_gate_arm
        CMP r1, #0
        MOVEQ r0, #0
        BXEQ lr
        MUL r3, r1, r2
        CMP r0, r3
        MOVHS r0, #1
        MOVLO r0, #0
        BX lr
        END
