; End-to-end BDOS test: create, write across allocation blocks, close,
; reopen, verify every byte, then leave the file for host-side inspection.
        org 0100h
        lxi sp,stackend
        lxi d,fcb
        mvi c,19
        call 5
        lxi d,fcb
        mvi c,22
        call 5
        inr a
        jz fail
        lxi d,buffer
        mvi c,26
        call 5
        xra a
        sta record
wrloop: lda record
        lxi h,buffer
        mvi b,128
fill:   mov m,a
        inr a
        inx h
        dcr b
        jnz fill
        lxi d,fcb
        mvi c,21
        call 5
        ora a
        jnz fail
        lxi h,record
        inr m
        mov a,m
        cpi 17
        jnz wrloop
        lxi d,fcb
        mvi c,16
        call 5
        inr a
        jz fail
        lxi h,fcb+12
        mvi b,24
clear:  mvi m,0
        inx h
        dcr b
        jnz clear
        lxi d,fcb
        mvi c,15
        call 5
        inr a
        jz fail
        xra a
        sta record
rdloop: lxi d,fcb
        mvi c,20
        call 5
        ora a
        jnz fail
        lda record
        lxi h,buffer
        mvi b,128
verify: cmp m
        jnz fail
        inr a
        inx h
        dcr b
        jnz verify
        lxi h,record
        inr m
        mov a,m
        cpi 17
        jnz rdloop
        lxi d,fcb
        mvi c,16
        call 5
        lxi d,passed
        jmp report
fail:   lxi d,failed
report: mvi c,9
        call 5
        mvi c,0
        jmp 5
passed: db 'DISK PASS: 17 records verified',13,10,'$'
failed: db 'DISK FAIL',13,10,'$'
record: db 0
fcb:    db 0,'MPMPORT DAT'
        ds 24
buffer: ds 128
        ds 256
stackend:
        db 0                    ; include zero-filled FCB and scratch in COM
        end
