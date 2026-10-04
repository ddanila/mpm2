#!/usr/bin/env python3
"""Boot the Juku target through real Fastboot/NetDisk USART traffic (POSIX)."""
import argparse
import json
import os
import pty
import select
import shutil
import subprocess
import tempfile
import time
import tty
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/juku'
ROM = 'spinoffs/jukuravi/network-rom/juku-network-rom-abi1.4-c10.bin'


def build_simulator(cosim):
    subprocess.run([os.environ.get('CC', 'cc'), '-O2', '-o', str(BUILD/'trace'),
                    *(str(cosim/'cosim'/name) for name in
                      ('trace.c', 'i8080.c', 'juk_disk.c', 'juku_fdc.c'))], check=True)
    if not (cosim/'build/jukuhost').exists():
        raise FileNotFoundError('Build the native host first: '
                                f'bash {cosim}/sync/jukuhost_linux_build.sh')


def run(cosim, commands=(), seconds=120, bad_header=False):
    out = Path(tempfile.mkdtemp(prefix='run-', dir=BUILD))
    volume = out/'a.img'
    shutil.copyfile(BUILD/'a.img', volume)
    if bad_header:
        # A malformed record count must never drive the loader into low RAM.
        with volume.open('r+b') as f:
            f.seek(120)
            f.write(b'\xff\xff')
    master, slave = pty.openpty()
    console, conslave = pty.openpty()
    tty.setraw(slave)
    tty.setraw(conslave)
    # Do not inherit fault injection or timing options from other experiments.
    env = {k: v for k, v in os.environ.items() if not k.startswith('JUKU_')}
    env.update(JUKU_USART_PTY=os.ttyname(slave), JUKU_USART_PIT_CLOCK='1',
               JUKU_USART_PIT_CPU_HZ='1700000', JUKU_REALTIME_HZ='1700000',
               JUKU_CHECKPOINT_PREFIX=str(out/'checkpoint'), JUKU_TRACE_BANK='0',
               JUKU_PC_HISTORY='1', JUKU_TRACE_TIMING='1', JUKU_S21_CONFIG='6',
               JUKU_DISABLE_SETTLE='1')
    transcript = bytearray()
    processes = []
    finished = False
    with (out/'sim.log').open('wb') as simlog, (out/'host.log').open('wb') as hostlog:
        try:
            sim = subprocess.Popen([str(BUILD/'trace'), str(cosim/ROM),
                                    '2000000000', '0', '34000'], cwd=out, env=env,
                                   stdout=subprocess.DEVNULL, stderr=simlog)
            processes.append(sim)
            host = subprocess.Popen([
                str(cosim/'build/jukuhost'), '--serial-fd', str(master),
                '--system', str(BUILD/'system.bin'), '--volume', str(volume),
                '--fast-stage', str(BUILD/'fastboot.bin'), '--network-rom',
                '--console-pty', os.ttyname(conslave), '--writable', '--verbose'],
                pass_fds=(master,), stdout=hostlog, stderr=subprocess.STDOUT)
            processes.append(host)
            deadline = time.monotonic()+seconds
            pending = iter(commands)
            while time.monotonic() < deadline and all(p.poll() is None for p in processes):
                if not select.select([console], [], [], 0.1)[0]:
                    continue
                data = os.read(console, 4096)
                transcript.extend(data)
                print(data.decode('ascii', errors='replace'), end='', flush=True)
                if bad_header and b'MP/M load failed\r\n' in transcript:
                    finished = True
                    break
                if transcript.endswith(b'0A>'):
                    if bad_header:
                        raise AssertionError('Corrupt system header reached MP/M')
                    command = next(pending, None)
                    if command is None:
                        finished = True
                        break
                    os.write(console, command.encode('ascii')+b'\r')
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
            for proc in processes:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for fd in (master, slave, console, conslave):
                os.close(fd)
            (out/'console.txt').write_bytes(transcript)
            (out/'run.json').write_text(json.dumps({
                'cosim': str(cosim), 'commands': list(commands),
                'bad_header': bad_header, 'finished': finished,
                'exit_codes': [p.returncode for p in processes]}, indent=2)+'\n')
    print(f'\nEvidence: {out}')
    if not finished:
        raise RuntimeError(f'MP/M sequence did not finish within {seconds}s; see {out}')
    if any(p.returncode != 0 for p in processes):
        raise RuntimeError(f'Simulator or host failed; see {out}')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cosim', type=Path, default=ROOT.parent/'8080-cosim')
    parser.add_argument('--seconds', type=float, default=120)
    parser.add_argument('--command', action='append', default=[])
    args = parser.parse_args()
    cosim = args.cosim.resolve()
    build_simulator(cosim)
    run(cosim, args.command, args.seconds)


if __name__ == '__main__':
    main()
