#!/usr/bin/env python3
"""End-to-end Juku checks, including persisted file data and loader rejection."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'targets/juku'))
from run_cosim import build_simulator, run


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_disk(path):
    image = path.read_bytes()
    directory = image[40960:45056]
    entries = [directory[i:i+32] for i in range(0, len(directory), 32)]
    entries = [e for e in entries if e[:12] == b'\0MPMPORT DAT']
    require(len(entries) == 1, 'Expected one MPMPORT.DAT directory extent')
    e = entries[0]
    require(e[12] == 0 and e[14] == 0 and e[15] == 17,
            'Wrong extent or record count for MPMPORT.DAT')
    require(e[16] >= 2 and e[17] >= 2 and e[16] != e[17],
            'File must span two distinct allocation blocks')
    actual = b''.join(image[40960+b*2048:40960+(b+1)*2048] for b in e[16:18])[:17*128]
    expected = bytes((record+i) & 255 for record in range(17) for i in range(128))
    require(actual == expected, 'Persisted network-disk file differs from test pattern')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cosim', type=Path, default=ROOT.parent/'8080-cosim')
    parser.add_argument('--seconds', type=float, default=180)
    args = parser.parse_args()
    cosim = args.cosim.resolve()
    build_simulator(cosim)
    good = run(cosim, ['DIR', 'RWTEST', 'PREEMPT', 'SHOW SPACE:'], args.seconds)
    console = (good/'console.txt').read_bytes()
    for text in (b'MP/M II V2.1', b'RWTEST', b'PREEMPT',
                 b'DISK PASS: 17 records verified',
                 b'PREEMPT PASS: two busy processes',
                 b'CLOCK PASS: delay completed', b'A: RW, Space:'):
        require(text in console, f'Missing console result: {text!r}')
    require(b'FAIL' not in console and b'Invalid Option' not in console,
            'Guest reported a failure')
    require(console.count(b'0A>') == 5, 'Commands did not all return to the prompt')
    require('irq=5' in (good/'sim.log').read_text(), 'No hardware frame interrupt observed')
    state = dict(line.split('=', 1) for line in (good/'checkpoint.state').read_text().splitlines()
                 if '=' in line)
    require(state['tpa_z80_prefix_fetches'] == '0', 'Guest executed a Z80 prefix')
    require(state['tpa_undocumented_opcode_fetches'] == '0', 'Guest executed an undocumented opcode')
    check_disk(good/'a.img')
    bad = run(cosim, seconds=30, bad_header=True)
    require(b'MP/M II V2.1' not in (bad/'console.txt').read_bytes(),
            'Malformed header must fail before kernel entry')
    result = {'passed': True, 'normal': str(good), 'malformed_header': str(bad)}
    (ROOT/'build/juku/acceptance.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: boot, commands, persisted disk I/O, preemption, delay, malformed header')


if __name__ == '__main__':
    main()
