#!/usr/bin/env python3
"""Build the standalone Juku target; the upstream emulator build is unchanged."""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path
from generate import generate
from toolchain import build_tools

ROOT = Path(__file__).resolve().parents[2]

def crc16(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--zmac', help='use an existing zmac instead of bundled tools')
    ap.add_argument('--zx0', help='use an existing ZX0 instead of bundled tools')
    args = ap.parse_args()
    out = ROOT / 'build/juku'
    out.mkdir(parents=True, exist_ok=True)
    if not args.zmac or not args.zx0:
        zmac, zx0 = build_tools()
        args.zmac = args.zmac or str(zmac)
        args.zx0 = args.zx0 or str(zx0)
    def assemble(src, name, prefix=''):
        path = out / (name + '.asm')
        path.write_text(prefix + src.read_text())
        subprocess.run([args.zmac, '-8', '-I', str(ROOT/'third_party/juku-common/platform'), '--oo', 'cim,lst', '--od', str(out), str(path)], check=True)
        return (out / (name + '.cim')).read_bytes()
    src = ROOT / 'targets/juku'
    a = assemble(src/'xios.asm', 'xios0', 'BASE equ 0\n')
    b = assemble(src/'xios.asm', 'xios1', 'BASE equ 0100h\n')
    if len(a) != len(b):
        raise ValueError('XIOS size depends on relocation')
    bitmap = bytearray((len(a)+7)//8)
    for i,(x,y) in enumerate(zip(a,b)):
        if x != y:
            if (y-x)&255 != 1:
                raise ValueError(f'Non-page relocation at {i:x}')
            bitmap[i//8] |= 0x80 >> (i%8)
    header = bytearray(256)
    struct.pack_into('<H',header,1,len(a))
    (out/'RESXIOS.SPR').write_bytes(header+a+bitmap)
    gen = generate(out)
    loader = assemble(src/'loader.asm', 'loader',
                      f'EXPECTED_RECORDS equ {len(gen.output)//128}\n'
                      f'EXPECTED_XDOS equ {gen.xdos.base}\n')
    if len(loader) > 0x1000:
        raise ValueError('Loader overlaps its cache/stack')
    # C8+ embedded decompressor writes 9000..D5FF and enters BE00.
    payload = bytearray(0x4600)
    payload[:len(loader)] = loader
    copy = ('        org 0be00h\n        di\n        lxi sp,02f00h\n'
            '        lxi h,09000h\n        lxi d,0300h\n'
            f'        lxi b,{len(loader)}\n'
            'copy:   mov a,m\n        stax d\n        inx h\n        inx d\n'
            '        dcx b\n        mov a,b\n        ora c\n        jnz copy\n'
            '        jmp 0300h\n        end\n')
    copysrc = out/'copy-source.asm'
    copysrc.write_text(copy)
    code = assemble(copysrc,'copy')
    payload[0x2e00:0x2e00+len(code)] = code
    identity = json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (src/'xios.asm', src/'loader.asm', out/'MPM.SYS')}, sort_keys=True).encode()
    payload[0x1000:0x1000+len(identity)] = identity
    (out/'payload.bin').write_bytes(payload)
    subprocess.run([args.zx0,'-f','-c',str(out/'payload.bin'),str(out/'payload.zx0')],check=True)
    compressed = (out/'payload.zx0').read_bytes()
    # The embedded source identity also keeps this small bootstrap above
    # the unchanged V16 minimum compressed payload size.
    if not 256 <= len(compressed) < 0x2800:
        raise ValueError(f'Fastboot compressed length out of range: {len(compressed)}')
    core = bytearray(128)
    core[:11] = b'\xc3\x00\x03JF16\x01\x00\x00\x00'
    descriptor = b'ZG'+crc16(payload).to_bytes(2,'big')+len(compressed).to_bytes(2,'big')+crc16(compressed).to_bytes(2,'big')
    (out/'fastboot.bin').write_bytes(core+descriptor+compressed)
    system = bytearray(512)
    system[:8] = b'JUKURM1\x1a'
    struct.pack_into('<HHHH',system,8,0x9000,0xbe00,len(payload),crc16(payload))
    (out/'system.bin').write_bytes(system+payload)
    for name in ('rwtest', 'preempt'):
        data = assemble(src/(name+'.asm'),name)
        (out/(name.upper()+'.COM')).write_bytes(data)
    # CP/M-format disk: eight reserved tracks, no physical-sector skew.
    image = bytearray(b'\xe5'*(80*40*128))
    if len(gen.output) > 8*40*128:
        raise ValueError('MPM.SYS exceeds reserved tracks')
    image[:len(gen.output)] = gen.output
    block = 2
    directory = 8*40*128
    entry = 0
    # One 32 KiB physical extent (EXM=1), up to 16 allocation blocks each.
    for file in sorted((ROOT/'bin/dri').glob('*.PRL')) + sorted(out.glob('*.COM')):
        data = file.read_bytes()
        for offset in range(0,len(data),32768):
            chunk = data[offset:offset+32768]
            records = (len(chunk)+127)//128
            count = (len(chunk)+2047)//2048
            if block+count > 180 or entry >= 128:
                raise ValueError('Distribution does not fit Juku volume')
            e = bytearray(32)
            e[1:12] = file.stem.upper().encode().ljust(8)+file.suffix[1:].upper().encode().ljust(3)
            extent = offset//16384 + (records-1)//128
            e[12] = extent&31
            e[14] = extent>>5
            e[15] = ((records-1)%128)+1
            e[16:16+count] = bytes(range(block,block+count))
            image[directory+entry*32:directory+(entry+1)*32] = e
            start = directory+block*2048
            image[start:start+len(chunk)] = chunk
            block += count
            entry += 1
    (out/'a.img').write_bytes(image)
    (out/'map.json').write_text(json.dumps({'system_base':gen.image_base,'system_top':0xd600,'user_bytes':gen.image_base-256,'xdos_entry':gen.xdos.base,'xios_base':gen.bnkxios.base,'disk_boot_tracks':8},indent=2)+'\n')
    print(f'Juku target built in {out}; user area {gen.image_base-256} bytes')

if __name__ == '__main__':
    main()
