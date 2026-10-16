# ios-sweet

Porting Apple's XNU kernel (the iOS 16 generation, xnu-8796) to the **Redmi Note 10 Pro** (`sweet`, Qualcomm SM7150 / Snapdragon 732G).

The goal is iOS 16 on a non-Apple phone. The port now boots real Apple iOS 16.7.16 (20H392) userspace from internal UFS storage: dyld loads the shared cache, launchd runs boot tasks, and Apple system daemons execute on the Snapdragon CPU.

**There is no working iOS GUI yet.** SpringBoard and backboardd reach display initialization and fail because the port does not provide an IOMobileFramebuffer display service. This is experimental bring-up, with incomplete drivers and security substitutes.

## Status

Status as of **2026-10-17**, based on the hardware observations and research in [`NOTES.md`](NOTES.md).

| Area | Current state |
| --- | --- |
| Boot shim and framebuffer console | Working on hardware via temporary `fastboot boot` |
| Plain arm64 XNU, 16K pages, interrupts and timers | Working on hardware |
| CPU support | One XNU boot CPU; secondary CPU power-on verified separately in the shim, not XNU SMP |
| Kernel-managed RAM | About 3.95 GiB in the upper DDR bank, verified on hardware |
| Internal UFS storage | Root device reads and writes the existing `userdata` partition |
| Root filesystem | Journaled, case-sensitive HFS+ image containing iPhone X iOS userspace and cryptex contents |
| Apple dyld and launchd | Shared cache maps; boot tasks run and LaunchDaemons start on hardware |
| Apple services | Many execute, including bluetoothd, powerd and runningboardd; this does not establish working radios or other hardware |
| Recent daemon fixes | Recorded watchdogd, CommCenter, identityservicesd and logd crashes resolved in subsequent phone boots |
| SpringBoard and backboardd | Execute, then fail at missing main-display initialization |
| GUI, GPU acceleration and touchscreen | Not working; display and IOSurface support are the next work |

### Current work: getting pixels from the iOS window server

The chosen approach is **CPU rendering plus a kernel IOMobileFramebuffer service**,
with display output kept separate from a possible future Adreno driver. QuartzCore
contains a software renderer, but its selection and operation on this port have
not yet been verified. Display discovery has been traced to device-tree display
nodes and matching IOMobileFramebuffer services. IOSurface buffer handling, swaps
and display notifications still need implementation.

The latest documented kernel is **0045** (CI run `38961814194`), used by
`shim/out/shim-boot-0045n.img`. The latest recorded phone result uses root image
**v7**. Image **v8** is prepared to send SpringBoard/backboardd logs to the console;
its resulting phone output is not yet recorded. Other unresolved crashes include
mediaserverd, lockdownd and locationd.

AppleKeyStore and watchdog support are limited bring-up implementations. The port
also relaxes root authentication and code-signing policies and uses an unsecured
launchd cache. These do not provide Apple's normal security guarantees. Starting a
service is distinct from providing its underlying hardware functionality.

The active handoff at the top of [`NOTES.md`](NOTES.md) records exact boot results,
artifacts, build IDs and the next action. Older entries preserve superseded states.

## How it boots

```
ABL (stock bootloader)
  -> fastboot boot shim-boot.img     (temporary kernel/shim image)
     -> shim: own MMU setup, reads the live FDT, loads the payload from the ramdisk
        -> XNU Mach-O + generated Apple Device Tree + boot_args
           -> XNU -> UFS root device -> journaled HFS+ on userdata
              -> Apple dyld + shared cache -> launchd -> boot tasks and daemons
```

- **No serial.** The debug UART is wired as SPI on sweet, so the screen is the only debug channel. The shim and the XNU patches draw stage markers, kprintf output and panics straight into the framebuffer ABL leaves at `0x9c000000`. Progress is read from phone photos or QEMU framebuffer text snapshots.
- **Storage is persistent.** The iOS root image replaces Android userdata; Android cannot boot normally with that data partition. Bootloaders, recovery, modem/persist partitions and backups are preserved. No GPT changes were needed.

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
| `tools/mkiosroot.sh` | Repackages OS, SystemOS and AppOS images into a journaled HFS+ root |
| `tools/patch-launchd-plist.py` | Enables console logging for selected launchd jobs and disables panic-on-crash keys |
| `tools/sweet-crash.py` | Symbolicates console crash reports against the shared cache and root binaries |
| `tools/sparsediff.py` | Builds sparse image differences; requires an exact unchanged baseline |
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
| 0016 | Built-in SWEET device-tree platform expert |
| 0017 | Select virtual timer PPI from the device tree (phone 19, QEMU 27) |
| 0018 | Single boot CPU driver with processor registration and SGI validation |
| 0019 | Built-in Apple OSS libpthread kernel provider |
| 0020 | Portable BearSSL AES support |
| 0021-0024 | RAM-disk root, mockfs fixes and built-in SHA-256 |
| 0025 | Initial built-in AMFI interface without entitlements |
| 0026-0027 | Built-in Apple OSS HFS and BearSSL MD5 |
| 0028-0031 | UFS root device, unsealed root and opt-in UFS/root writes |
| 0032-0033 | BearSSL SHA-1 and SHA-384/512 |
| 0034 | UFS DMA address checks for memory above 4 GiB |
| 0035-0036 | XML entitlements and signed/platform-binary status for bring-up |
| 0037 | Enable bindfs |
| 0038 | Limited AppleKeyStore service |
| 0039 | Disable core dumps by default |
| 0040-0042 | Watchdog service and quieter HFS/exec console output |
| 0043-0044 | Console crash reports, backtraces and exit-reason text |
| 0045 | Watchdog PMU-primary compatibility |

CI runs the numbered staging scripts to fetch the pinned libpthread, BearSSL and
HFS sources before applying the patches.

## Build and boot

Kernel (CI):

```sh
gh workflow run xnu.yml -R dipa-studio/ios-sweet
gh run download RUN_ID -R dipa-studio/ios-sweet -n xnu-kernel -D xnu/out
```

Replace `RUN_ID` with the successful build being used. The examples below run
from the repository root. Building the shim needs `aarch64-linux-gnu-gcc`,
`mkbootimg`, and the locally extracted stock DTB at `dtb/boot_unpacked/dtb`.

Phone payload for an **already provisioned iOS root** on `userdata`:

```sh
mkdir -p shim/out
tools/mkadt.py shim/out/sweet.adt --highmem
tools/mkpayload.py xnu/out/kernel.development.sweet shim/out/sweet.adt shim/out/payload.bin \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1'
shim/build.sh out/payload.bin
```

Boot it (phone in fastboot):

```sh
fastboot boot shim/out/shim-boot.img
```

This temporarily loads the boot image, but `ufsrw=1 rootrw=1` permits persistent
writes to the iOS root. Without an appropriate root image, this is not a complete
installation procedure.

`tools/mkiosroot.sh OS.dmg SYSTEMOS.dmg APPOS.dmg OUT.img [SIZE]` builds the base
root image (default 16 GiB), using `apfs-fuse`, `rsync`, HFS+ tools and sudo. The
latest diagnostic launchd plist changes are a separate step; see `NOTES.md`.
Provisioning replaces Android userdata. Preserve partition backups and keep writes
limited to the existing `userdata` partition. Large images must be converted to
Android sparse format for this device's fastboot download limit. A sparse diff is
valid only when its old image exactly matches the on-device contents; writable
boots invalidate that assumption.

Apple firmware, extracted userspace and root images are local artifacts and are
not included in this repository.

## Quick QEMU iteration

For a minimal userspace check, use the same kernel with a QEMU ADT and a locally
prepared HFS+ test root containing the static test init (the historical
`research/root-hfs.img`). This does not boot the full iOS root or emulate UFS:

```sh
mkdir -p research
tools/mkadt.py research/qemu.adt --qemu
tools/mkpayload.py xnu/out/kernel.development.sweet research/qemu.adt research/qemu.bin \
    --ramdisk research/root-hfs.img \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=md0'
tools/qemu-sweet.py research/qemu.bin research/qemu-run --secs 150 \
    --kernel xnu/out/kernel.development.sweet --fail-on-panic
cat research/qemu-run/result.json research/qemu-run/fb.txt
```

Requires `qemu-system-aarch64` and `llvm-nm`. The optional `--kernel` must match
the payload: its font decodes the framebuffer exactly, without OCR. A visible
panic returns exit code 2 with `--fail-on-panic`; incomplete or blank decoding
returns 3. `-noprogress` prevents the graphical progress indicator from drawing
over console text. `fb.txt` contains screen rows
in screen order; the console wraps, so this is not a full chronological log.
`no_panic_observed` only describes the snapshot; check `regs.txt` and the screen
for stalls. QEMU virt covers generic ARM kernel execution; Qualcomm hardware,
the bootloader, panel and PSCI conduit still require phone validation.

## Key hardware facts

- RAM has low and upper banks. Current phone payloads use `--highmem`: `0x100000000` + `0xfcc00000` (about 3.95 GiB), above the low-bank carve-outs. The original fallback is `0xb0000000` + `0x4d000000` (about 1.2 GiB). Mapping protected Qualcomm carve-outs cacheable faults.
- GICv3 with security extensions: Group 0 is secure, so the timer must go through Group 1 IRQ (vtimer INTID 19), not FIQ like on Apple silicon.
- PSCI over `smc` (not `hvc`), 19.2 MHz timer, 8 cores, ARMv8.2 without PAC.
- Panel: 1080x2400 DSC video mode, continuous splash, no refresh kick needed.

More in `NOTES.md`.
