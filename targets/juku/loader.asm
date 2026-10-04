ROM_ABI_EXTENDED equ 1
ROM_ABI_HOSTSERVICES equ 1
        include "rom-abi.inc"
; Loaded by the unchanged C8+ Fastboot ROM, then copied to low RAM.
; SPDX-License-Identifier: GPL-3.0-or-later
        org 0300h
start:  di
        lxi sp,02f00h
        call JCGINITADDR
        ora a
        jnz failure
        mvi a,1
        call JCGSERINITADDR
        call JCGKEYINITADDR
        lxi h,mode
        call JCGNETDISKADDR
        call JCGCONINITADDR
        mvi c,0
        call JCGHOSTADDR
        mvi c,10
        call JCGHOSTADDR
        ora a
        jnz nocaps
        inx h
        inx h
        mov a,m
        mvi c,1
        call JCGHOSTADDR
nocaps:
        lxi h,banner
        call print
        ; The reserved disk tracks contain DRI's MPM.SYS record order.
        call readnext
        lxi h,0d580h
        shld request+6
        call readnext
        lhld 0d578h              ; record count at SYSTEM.DAT+120
        mov a,h
        cpi EXPECTED_RECORDS/256
        jnz failure
        mov a,l
        cpi EXPECTED_RECORDS mod 256
        jnz failure
        lda 0d500h
        cpi 0d5h
        jnz failure
        lda 0d50bh
        cpi EXPECTED_XDOS/256
        jnz failure
        lhld 0d578h
        dcx h
        dcx h
        shld remaining
        lxi h,0d500h
loadloop:
        lxi d,0ff80h
        dad d
        shld request+6
        call readnext
        lhld remaining
        dcx h
        shld remaining
        mov a,h
        ora l
        lhld request+6
        jnz loadloop
        lda 0d50bh              ; XDOS entry page
        mov h,a
        mvi l,0
        pchl
readnext:
        lxi h,request
        call JCGNETDISKADDR
        ora a
        jnz failure
        lxi h,request+5
        inr m
        mov a,m
        cpi 41
        rnz
        mvi m,1
        lhld request+3
        inx h
        shld request+3
        ret
print:  mov a,m
        ora a
        rz
        push h
        push psw
        call JCGCONOUTADDR
        pop psw
        mvi c,4
        call JCGHOSTADDR
        pop h
        inx h
        jmp print
failure:
        lxi h,error
        call print
        di
halted: hlt
        jmp halted
banner: db 13,10,'Juku MP/M II loader',13,10,0
error:  db 13,10,'MP/M load failed',13,10,0
remaining: dw 0
mode:   db 1,2,3,0,0,0,0,0,0,0
request: db 1,0,0
        dw 0
        db 1
        dw 0d500h,02000h
        end
