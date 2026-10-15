# ios-sweet

Porting Apple's XNU kernel (the iOS 16 generation, xnu-8796) to the **Redmi Note 10 Pro** (`sweet`, Qualcomm SM7150 / Snapdragon 732G).

The goal is iOS 16 on a non-Apple Android phone. Right now the work is kernel bring-up: getting an open-source XNU build to boot on Qualcomm hardware, one crash at a time.

## Status

| Milestone | State |
| --- | --- |
| Bare-metal shim boots via `fastboot boot`, draws to the panel | done |
| GICv3 Group 1 interrupts, timers, SGIs, PSCI SMP verified | done |
| 16K-granule MMU verified on the Kryo 470 | done |
| Plain arm64 (no PAC) SWEET XNU config builds in CI | done |
| XNU reaches `arm_init`, `arm_vm_init`, `pmap_bootstrap` | done |
| Framebuffer kprintf console, VM/zones, scheduler, IPC, KDP up | done |
| Allocator RNG without corecrypto (patch 0013) | verified in QEMU and on hardware |
| Registered kernel PRNG (patch 0014) | verified in QEMU |
| Missing trust-cache providers (patch 0015) | handled; verified in QEMU |
| IOKit platform (GIC, PMGR, platform expert), userland | next |

The live, detailed log is in [`NOTES.md`](NOTES.md). Its "Agent handoff" section always holds the current blocker, latest CI run, image hashes and the next step.

## How it boots

```
ABL (stock bootloader)
  -> fastboot boot shim-boot.img     (temporary, nothing is flashed)
     -> shim: own MMU setup, reads the live FDT, loads the payload from the ramdisk
        -> XNU Mach-O + generated Apple Device Tree + boot_args
           -> start_first_cpu -> arm_init -> ...
```

- **No serial.** The debug UART is wired as SPI on sweet, so the screen is the only debug channel. The shim and the XNU patches draw stage markers, kprintf output and panics straight into the framebuffer ABL leaves at `0x9c000000`. Progress is read from phone photos.
- The shim resets itself via PSCI when done, so the phone comes back to Android on its own.

## Layout

| Path | What |
| --- | --- |
| `shim/` | Bare-metal boot shim (C + asm), `./build.sh [payload]` -> `out/shim-boot.img` |
| `xnu/patches/` | XNU patch series, applied in order by CI |
| `.github/workflows/xnu.yml` | Kernel build on GitHub macOS runners via [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build) |
| `tools/mkadt.py` | Builds the minimal Apple Device Tree from sweet's real MMIO layout |
| `tools/mkpayload.py` | Packs kernel + ADT + command line into the shim payload |
| `tools/qemu-sweet.py` | Boot a payload in QEMU virt (use an ADT from `mkadt.py --qemu`), dumps the screen to PNG |
| `tools/xnu-cc.py` | Local single-file cross-compile using a CI build log, to check patches before spending a CI run |
| `tools/adt.py`, `remotezip.py` | Read Apple device trees, pull single files out of IPSWs |
| `tools/unpack_bootv2.py` | Unpack Android boot.img v2 |
| `NOTES.md` | Hardware facts, design decisions, full bring-up history |
| `AGENTS.md` | Rules for coding agents working on the repo |

Not in git (see `.gitignore`): `backup/` partition dumps, `dtb/` live device trees, `recovery/` OrangeFox, `research/` downloaded sources and build trees, and all build outputs. Those contain IMEI, calibration and serial data, or Apple artifacts.

## Patch series

| # | Patch |
| --- | --- |
| 0001-0002 | New clang compatibility |
| 0003 | Framebuffer serial console |
| 0004 | SWEET machine config |
| 0005 | Non-PAC (plain arm64) build fixes |
| 0006 | SWEET master config, open-source asm pmap |
| 0007-0009 | Stub Apple-internal headers, closed-lib gaps, Apple-SoC-only exports |
| 0010 | Early framebuffer debug markers (MMU off and on) |
| 0011 | Physmap block-alignment padding fix |
| 0012 | Keep the debug console alive after TTBR0 teardown |
| 0013 | Per-CPU allocator RNG without corecrypto |
| 0014 | Built-in HMAC-SHA256 kernel PRNG and entropy hashing |
| 0015 | Explicitly unavailable trust-cache service without Image4/AMFI |

## Build and boot

Kernel (CI):

```sh
gh workflow run xnu.yml -R dipa-studio/ios-sweet
gh run download -R dipa-studio/ios-sweet -n xnu-kernel -D xnu/out
```

Payload and boot image (needs `aarch64-linux-gnu-gcc` and `mkbootimg`):

```sh
tools/mkadt.py shim/out/sweet.adt
tools/mkpayload.py xnu/out/kernel.development.sweet shim/out/sweet.adt shim/out/payload.bin \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam'
shim/build.sh out/payload.bin
```

Boot it (phone in fastboot):

```sh
fastboot boot shim/out/shim-boot.img
```

Never `fastboot flash` anything for bring-up. Android (PixelOS) stays installed and untouched.

## Quick QEMU iteration

Use the same kernel with a QEMU ADT (virt GIC addresses and timer frequency):

```sh
tools/mkadt.py research/qemu.adt --qemu
tools/mkpayload.py xnu/out/kernel.development.sweet research/qemu.adt research/qemu.bin \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam'
tools/qemu-sweet.py research/qemu.bin research/qemu-run --secs 10 \
    --kernel xnu/out/kernel.development.sweet --fail-on-panic
cat research/qemu-run/result.json research/qemu-run/fb.txt
```

Requires `qemu-system-aarch64` and `llvm-nm`. The optional `--kernel` must match
the payload: its font decodes the framebuffer exactly, without OCR. A visible
panic returns exit code 2 with `--fail-on-panic`. `fb.txt` contains screen rows
in screen order; the console wraps, so this is not a full chronological log.
`no_panic_observed` only describes the snapshot; check `regs.txt` and the screen
for stalls. QEMU virt covers generic ARM kernel execution; Qualcomm hardware,
the bootloader, panel and PSCI conduit still require phone validation.

## Key hardware facts

- RAM at `0x80000000`; XNU gets `0xb0000000` + `0x4d000000`, above every Qualcomm XPU carve-out (mapping those cacheable faults).
- GICv3 with security extensions: Group 0 is secure, so the timer must go through Group 1 IRQ (vtimer INTID 19), not FIQ like on Apple silicon.
- PSCI over `smc` (not `hvc`), 19.2 MHz timer, 8 cores, ARMv8.2 without PAC.
- Panel: 1080x2400 DSC video mode, continuous splash, no refresh kick needed.

More in `NOTES.md`.
