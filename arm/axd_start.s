        AREA startup, CODE, READONLY
        CODE32
        IMPORT __main
        EXPORT _start
        ENTRY
; 先初始化C运行库，main正常返回后由运行库退出。
_start
        B __main
        END
