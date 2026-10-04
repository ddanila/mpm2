#!/usr/bin/env python3
"""Juku's unbanked system layout, using the shared SPR relocator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from gensys import SystemConfig, SystemGenerator

class JukuGenerator(SystemGenerator):
    def setup_memory_segments(self):
        # One common address space. Segment zero owns the resident OS and
        # reserved firmware/video region; segment one owns the transient area.
        # DRI GENSYS uses BNKBDOS/BNKXDOS even in an unbanked configuration.
        if self.cur_base < 0x20:
            raise ValueError('Juku resident system leaves less than 8 KiB user RAM')
        self.system_data[16:24] = bytes((self.cur_base, 256-self.cur_base,
                                       0x80, 0, 0, self.cur_base, 0, 0))
        self.system_data[15] = 2

def generate(out):
    root = Path(__file__).resolve().parents[2]
    cfg = SystemConfig(mem_top=0xD5, common_base=0, num_consoles=1,
        num_printers=0, bank_switched=False, z80_cpu=False,
        sys_call_stks=True, banked_bdos=True, day_file=False,
        ticks_per_second=50, num_mem_segments=1,
        total_locked_records=16, total_open_files=16,
        spr_dir=str(root / 'bin/dri'),
        resbdos_spr='RESBDOS.SPR', xdos_spr='XDOS.SPR',
        bnkxios_spr=str(out / 'RESXIOS.SPR'), bnkbdos_spr='BNKBDOS.SPR',
        bnkxdos_spr='BNKXDOS.SPR', tmp_spr='TMP.SPR')
    gen = JukuGenerator(cfg)
    gen.generate()
    gen.write_output(out / 'MPM.SYS')
    (out / 'memory.bin').write_bytes(gen.mem_image + gen.system_data)
    return gen
