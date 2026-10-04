# Juku MP/M II target

This separate target boots Digital Research MP/M II 2.1 on the Juku E5101/E5104
8080 hardware model in `8080-cosim`, using the existing JukuNet C10 ROM and
native `jukuhost`. The upstream Z80 emulator target is unchanged.

The current layout leaves **27.5 KiB** (`0100h..6EFFh`) for user programs,
with one shared address space, one console, and a 400 KiB network disk A:.
Processes can share that memory and receive timer-driven preemption. There
are no extra memory banks or independent address spaces. Physical-hardware
qualification and a rebuild of the DRI nucleus from source remain future work.

Development lives on `ports/juku` in `ddanila/mpm2`. Keep the fork's default
branch (`main`) for upstream synchronization, and bring upstream updates into
the port branch separately.

## Build

Requirements: Python 3, a C and C++ compiler, Bison, and Git.

```sh
git submodule update --init third_party/juku-common
python3 targets/juku/build.py
```

The build compiles the bundled zmac 18oct2022 and ZX0 2.2 tools, then assembles
the XIOS, loader and test programs as Intel 8080 code. For faster subsequent
builds, reuse the tools:

```sh
python3 targets/juku/build.py \
  --zmac build/juku/tools/zmac --zx0 build/juku/tools/zx0
```

The nucleus and utilities come from the preserved DRI 2.1 distribution in
`bin/dri`. This target reuses `tools/gensys.py` for SPR relocation and system
generation, with a target-specific unbanked memory segment table. It does not
require the upstream emulator's SSH libraries or PL/M toolchain.

Outputs go to `build/juku`: `RESXIOS.SPR`, `MPM.SYS`, `memory.bin`, `map.json`,
`system.bin`, `fastboot.bin`, and `a.img`, plus intermediate assembly listings.
Use **matching** `system.bin`, `fastboot.bin`, and `a.img` from the same build.

## Simulator tests

Use a sibling `8080-cosim` checkout with the C10 ROM and native host. The
initial port was tested against commit
`390ee55b87da256d360b302c36d7ce2ca7c0f0dd`.

```sh
bash ../8080-cosim/sync/jukuhost_linux_build.sh
python3 tests/juku/acceptance.py
```

The test compiles the C hardware simulator and connects it to the production
host over PTYs. All disk and remote-console traffic crosses the emulated
USART and the ROM protocol implementation; no disk or BDOS traps are used.
It checks:

- Boot to the MP/M II 2.1 prompt, `DIR`, and the DRI `SHOW SPACE:` utility.
- BDOS create/write/close/reopen/read of 17 records spanning two allocation
  blocks, plus independent comparison of the persisted host-side file.
- Preemption between two busy processes that cannot cooperate through calls,
  explicit worker termination, and the timer delay service.
- No Z80-prefix or undocumented-opcode fetches in the simulator's TPA counters.
- Rejection of a corrupted `MPM.SYS` record count before entering the nucleus.

Each boot gets an isolated writable disk image and journal. Logs, console
transcripts and final RAM/CPU snapshots remain in `build/juku/run-*`;
`build/juku/acceptance.json` identifies successful test runs. The test takes
roughly a minute or two at the modeled 1.7 MHz and 19,200 baud.

For a custom command sequence:

```sh
python3 targets/juku/run_cosim.py --command DIR --command 'SHOW SPACE:'
```

Both scripts accept `--cosim /path/to/8080-cosim` and `--seconds TIMEOUT`.
The PTY runner requires POSIX; the documented native host build is for Linux.

### Initial validation result

The bundled-tool build and complete acceptance suite passed with the simulator
revision above. The normal boot ran all four commands and returned to `0A>`
after each. Its significant output was:

```text
DISK PASS: 17 records verified
PREEMPT PASS: two busy processes
CLOCK PASS: delay completed
A: RW, Space:       210k
```

The host-side file comparison also passed. A separate boot with a corrupted
record count printed `MP/M load failed` without entering the nucleus. These
are simulator results, not physical-hardware qualification. Generated images,
journals, and machine-specific logs stay under the ignored `build/juku` tree;
rerun the suite to produce evidence for a new checkout.

## Architecture and limits

The unchanged ROM's Fastboot V16 installs a `9000h..D5FFh` bootstrap payload
and enters `BE00h`. It copies a loader to `0300h`, which reads `MPM.SYS` from
eight reserved NetDisk tracks, checks the expected header geometry, and enters
XDOS. The disk has 80 tracks of 40 128-byte records, 2 KiB allocation blocks,
128 directory entries, and no sector skew. It contains the DRI PRL utilities
and two small acceptance-test COM programs. B: is not advertised.

DRI's BNKBDOS and BNKXDOS modules are also used by its original nonbanked
configuration; their names do not imply additional physical RAM here.
SYSTEM.DAT is at `D500h`. `D600h..D7FFh` belongs to the existing ROM ABI gate,
framebuffer helper and workspace; `D800h..FFFFh` is the ROM/framebuffer window.
`map.json` reports the resident/user split for each build.

The XIOS combines local keyboard/display and N4 remote access into one
console. It uses ROM NetDisk and IRQ5 frame interrupts through the 8259 in
MCS-80 CALL mode. The simulator frame period is 34,000 cycles at 1.7 MHz
(50 Hz). ROM operations use a private stack and hold interrupts disabled
because the firmware has shared mutable state. Consequently, network I/O
blocks scheduling and loses clock ticks; this is not a wall-clock-accurate
or low-latency multitasking implementation under I/O load. Pure CPU tasks
can preempt at the frame rate.

One transient memory segment means this first target does not offer the
banked emulator's ability to load several independent large applications.
Resident processes or programs deliberately sharing memory can multitask.
The tests exercise that case. They do not qualify local keyboard behavior,
physical serial timing, or arbitrary CP/M applications on real hardware.

## Tool provenance

`third_party/juku-common` pins the shared ROM ABI definitions. The bundled
zmac and ZX0 source snapshots match the tools in `ddanila/cpm-plus-juku` at
commit `61b2d5397589e794c0381aa836b7a0da2217e6c8`; upstream notices and licenses
are retained beside their sources. ZX0 uses classic `-c` format for the ROM's
8080 decompressor. The DRI materials retain their existing repository terms.
