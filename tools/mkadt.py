#!/usr/bin/env python3
"""Build the minimal Apple Device Tree that the SWEET xnu needs to boot.

Only what the early boot path actually reads (see NOTES.md); every MMIO
address comes from the sweet live FDT. Usage:  mkadt.py OUT.adt [--dump] [--qemu]
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

# Kernel-managed RAM: above every Qualcomm XPU carve-out (see NOTES.md)
PHYS_BASE = 0xb0000000
MEM_SIZE = 0x4d000000
# /arm-io children are relative to this; it must not be 0 (serial_init bails)
SOC_BASE = 0x01000000

GICD, GICD_SIZE = 0x17a00000, 0x10000
GICR, GICR_SIZE = 0x17a60000, 0x100000
FB, FB_SIZE = 0x9c000000, 0x1700000
FB_W, FB_H, FB_STRIDE = 1080, 2400, 1080 * 4
TIMEBASE = 19200000
# QEMU virt (-M virt,gic-version=3 -cpu cortex-a76): GICD/GICR and the generic timer's CNTFRQ
QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE = 0x08000000, 0x080a0000, 62500000

u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def build(seed=None, qemu=False):
    """qemu=True: same tree, but with QEMU virt's GIC addresses and CNTFRQ (tools/qemu-sweet.py)."""
    gicd, gicr, timebase = (QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE) if qemu else (GICD, GICR, TIMEBASE)
    seed = seed if seed is not None else os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(PHYS_BASE)),
        ('dram-size', u64(MEM_SIZE)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('firmware-version', cstr('sweet-shim')),
        ('system-firmware-version', cstr('sweet-shim')),
    ], [node('memory-map', [ph()])])

    cpu0 = node('cpu0', [
        ph(),
        ('device_type', cstr('cpu')),
        ('compatible', cstr('qcom,kryo470') + cstr('ARM,v8')),
        ('reg', u32(0)),			# start.s: CPU number = MPIDR Aff0 (0 on sweet)
        ('cpu-id', u32(0)),
        ('state', cstr('running')),
        ('timebase-frequency', u32(timebase)),
        ('clock-frequency', u32(1804800000)),
        ('bus-frequency', u32(100000000)),
        ('memory-frequency', u32(1866000000)),
        ('peripheral-frequency', u32(timebase)),
        ('fixed-frequency', u32(timebase)),
    ])
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)), ('#size-cells', u32(0))], [cpu0])

    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v3')),
        ('interrupt-controller', b''),
        ('reg', u64(gicd - SOC_BASE, GICD_SIZE, gicr - SOC_BASE, GICR_SIZE)),
    ])
    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('sweet-io')),
        ('compatible', cstr('sweet-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
    ], [gic])

    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(FB, FB_SIZE)),
        ('width', u32(FB_W)),
        ('height', u32(FB_H)),
        ('stride', u32(FB_STRIDE)),
    ])

    # pmap_compute_max_asids requires the node even when no overrides are set.
    # An absent pmap-max-asids property selects XNU's own MAX_ASIDS default.
    defaults = node('defaults', [ph()])

    return node('device-tree', [
        ph(),
        ('compatible', cstr('xiaomi,sweet') + cstr('qcom,sm7150') + cstr('AppleARM')),
        ('model', cstr('xiaomi,sweet')),
        ('target-type', cstr('sweet')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, fbcon])


if __name__ == '__main__':
    root = build(qemu='--qemu' in sys.argv)
    blob = adt.serialize(root)
    open(sys.argv[1], 'wb').write(blob)
    if '--dump' in sys.argv:
        adt.dump(adt.parse(blob)[0])
    print(f'{sys.argv[1]}: {len(blob)} bytes', file=sys.stderr)
