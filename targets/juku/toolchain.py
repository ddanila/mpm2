#!/usr/bin/env python3
"""Build the pinned zmac and ZX0 tools using a C/C++ compiler and Bison."""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_tools():
    out = ROOT / 'build/juku/tools'
    out.mkdir(parents=True, exist_ok=True)
    cc, cxx = os.environ.get('CC', 'cc'), os.environ.get('CXX', 'c++')

    def run(*args, **kwargs):
        subprocess.run([str(x) for x in args], check=True, **kwargs)

    src = ROOT / 'third_party/zmac'
    run(cc, '-O2', '-DMK_DOC', '-Wno-main', '-o', out/'docgen', src/'doc.c')
    shutil.copyfile(src/'doc.txt', out/'doc.txt')
    run(out/'docgen', cwd=out, stdout=subprocess.DEVNULL)
    run(os.environ.get('BISON', 'bison'), '--defines='+str(out/'parser.h'),
        '--output='+str(out/'parser.c'), src/'zmac.y')
    objects = []
    for source in (out/'parser.c', src/'doc.c', src/'mio.c', src/'zi80dis.cpp'):
        obj = out/(source.stem+'.o')
        run(cxx if source.suffix == '.cpp' else cc, '-O2', '-c',
            '-I'+str(out), '-I'+str(src), '-o', obj, source)
        objects.append(obj)
    run(cxx, '-o', out/'zmac', *objects)
    src = ROOT / 'third_party/zx0'
    run(cc, '-O2', '-o', out/'zx0',
        *(src/name for name in ('zx0.c', 'optimize.c', 'compress.c', 'memory.c')))
    return out/'zmac', out/'zx0'


if __name__ == '__main__':
    print(*build_tools(), sep='\n')
