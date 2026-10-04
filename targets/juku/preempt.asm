; Both processes spin without system calls. Completion therefore requires
; timer-driven preemption in both directions; cooperative dispatch cannot pass.
        org 0100h
        lxi sp,stackend
        lxi d,pd
        mvi c,144
        call 5
waitchild:
        lda childrunning
        ora a
        jz waitchild
        mvi a,1
        sta parentsaw
waitdone:
        lda childdone
        ora a
        jz waitdone
        ; Worker terminates itself before this task can run again.
        lxi d,passed
        mvi c,9
        call 5
        lxi d,3
        mvi c,141               ; also exercise clock flag 1 / delay list
        call 5
        lxi d,clockpassed
        mvi c,9
        call 5
        mvi c,0
        jmp 5
worker:
        mvi a,1
        sta childrunning
spin:   lda parentsaw
        ora a
        jz spin
        mvi a,1
        sta childdone
        lxi d,00ffh             ; allow termination of this system process
        mvi c,143               ; system processes require explicit terminate
        jmp 5
passed: db 'PREEMPT PASS: two busy processes',13,10,'$'
clockpassed: db 'CLOCK PASS: delay completed',13,10,'$'
childrunning: db 0
parentsaw: db 0
childdone: db 0
pd:     dw 0
        db 0,200
        dw workerentry
        db 'JUKUTEST'
        db 0,0ffh
        ds 36
        ds 256
workerentry: dw worker
        ds 256
stackend:
        end
