ROM_ABI_EXTENDED equ 1
ROM_ABI_HOSTSERVICES equ 1
        include "rom-abi.inc"
; Juku MP/M II resident XIOS. Intel 8080, unbanked RAM, JukuNet ROM ABI 1.4.
; SPDX-License-Identifier: GPL-3.0-or-later
        org BASE
        jmp commonbase
        jmp warmboot
        jmp const
        jmp conin
        jmp conout
        jmp empty
        jmp empty
        jmp empty
        jmp home
        jmp seldsk
        jmp settrk
        jmp setsec
        jmp setdma
        jmp read
        jmp write
        jmp ready
        jmp sectran
        jmp empty
        jmp polldev
        jmp startclock
        jmp stopclock
        jmp exitregion
        jmp maxconsole
        jmp systeminit
        db 0,0,0                 ; use MP/M's internal idle dispatcher
commonbase:
        jmp warmboot
swtuser: jmp 0
swtsys: jmp 0
pdisp:  jmp 0
xdos:   jmp 0
sysdat: dw 0
warmboot:
        mvi c,0
        jmp xdos
empty:  xra a
        ret
ready:  mvi a,0ffh
        ret
maxconsole:
        mvi a,1
        ret

; ROM calls need a private stack: MP/M internal stacks are only 40 bytes.
; No dispatcher or interrupt can enter the shared ROM workspace mid-call.
romcall:
        di
        shld romtarget+1
        lxi h,0
        dad sp
        shld romsp
        lxi sp,romstackend
        call romtarget
        lhld romsp
        sphl
        ret
romtarget:
        jmp 0
const:
        lxi h,JCGCONSTATADDR
        call romcall
        ora a
        jnz constret
        mvi c,2                  ; N4 console status
        lxi h,JCGHOSTADDR
        call romcall
constret:
        push psw
        call exitregion
        pop psw
        ret
conin:
        mvi c,131
        mvi e,0
        call xdos
        lxi h,JCGCONSTATADDR
        call romcall
        ora a
        jz remotein
        lxi h,JCGCONINADDR
        call romcall
        jmp constret
remotein:
        mvi c,3
        lxi h,JCGHOSTADDR
        call romcall
        jmp constret
conout:
        mov a,c
        push psw
        lxi h,JCGCONOUTADDR
        call romcall
        pop psw
        mvi c,4
        lxi h,JCGHOSTADDR
        call romcall
        jmp exitregion
polldev:
        mov a,c
        ora a
        jz const
        jmp ready
home:   lxi b,0
settrk: mov h,b
        mov l,c
        shld request+3
        ret
setsec: mov a,c
        inr a
        sta request+5
        ret
setdma: mov h,b
        mov l,c
        shld request+6
        ret
sectran:
        mov h,b
        mov l,c
        ret
seldsk:
        lxi h,0
        mov a,c
        cpi 1
        rnc
        sta request+2
        lxi h,dph0
        ret
read:   xra a
        jmp diskio
write:  mvi a,3
 diskio:
        sta request+1
        ; ROM expects HL=request. romcall uses HL for its target, so put
        ; a tiny adapter on the private stack path.
        lxi h,diskrom
        call romcall
        jmp constret
 diskrom:
        lxi h,request
        jmp JCGNETDISKADDR
startclock:
        mvi a,0ffh
        sta ticking
        ret
stopclock:
        xra a
        sta ticking
        ret
exitregion:
        lda preempt
        ora a
        rnz
        ei
        ret
systeminit:
        di
        ; PIC CALL address: ICW1=16h / ICW2=00h makes IRQ5 call 0014h.
        mvi a,0c3h
        sta 0014h
        lxi h,interrupt
        shld 0015h
        mvi a,016h
        out 0
        xra a
        out 1
        mvi a,0dfh
        out 1
        ei
        ret
interrupt:
        shld savehl
        pop h
        shld savepc
        push psw
        lxi h,0
        dad sp
        shld savesp
        lxi sp,intstackend
        push d
        push b
        mvi a,0ffh
        sta preempt
        lhld ticks
        inx h
        shld ticks
        lda ticking
        ora a
        jz second
        mvi c,133
        mvi e,1
        call xdos
second:
        lxi h,seconds
        dcr m
        jnz intdone
        mvi m,50
        mvi c,133
        mvi e,2
        call xdos
intdone:
        mvi a,020h
        out 0
        xra a
        sta preempt
        pop b
        pop d
        lhld savesp
        sphl
        pop psw
        lhld savepc
        push h
        lhld savehl
        jmp pdisp
request:
        db 1,0,0
        dw 0
        db 1
        dw 0080h,cache
; 80 logical tracks, 40 x 128-byte records, eight boot tracks.
; 180 allocation blocks of 2 KiB, 128 directory entries, no skew.
dph0:   dw 0,0,0,0,dirbuf,dpb,check0,alloc0
dpb:    dw 40
        db 4,15,1
        dw 179,127
        db 0c0h,0
        dw 32,8
preempt: db 0
ticking: db 0
seconds: db 50
ticks:  dw 0
savehl: dw 0
savepc: dw 0
savesp: dw 0
romsp:  dw 0
intstack: ds 128
intstackend:
romstack: ds 256
romstackend:
dirbuf: ds 128
check0: ds 32
alloc0: ds 23
cache: ds 1024
        db 0
        end
