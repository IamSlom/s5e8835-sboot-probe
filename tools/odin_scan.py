#!/usr/bin/env python3
"""Locate and decode the Odin data-plane state-conditional bounds check.

The Odin engine is a large PAC-built function with a distinctive 0x400-byte
stack frame. It tracks a relative offset, checks it against a session limit,
and arms the next transfer at an advancing destination pointer. The check is
gated on the packet flags: `(flags & ~4) == 2`. Any other flags value skips the
comparison and reaches the transfer arm with the offset unchecked.

This tool finds the engine by prologue, derives the session context page,
prints the flags gate and the checked/rejected targets, locates the setup
function that initialises the destination/size slots, reads the block-size
constant it loads, and lists direct callers. Static only; no device access.
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import firmware_inspect as fi

PACIBSP = 0xD503237F
ENGINE_PROLOGUE = (
    PACIBSP,      # pacibsp
    0xA9BC7BFD,   # stp x29, x30, [sp, #-0x40]!
    0xF9000BFC,   # str x28, [sp, #0x10]
    0xA90257F6,   # stp x22, x21, [sp, #0x20]
    0xA9034FF4,   # stp x20, x19, [sp, #0x30]
    0x910003FD,   # mov x29, sp
    0xD11003FF,   # sub sp, sp, #0x400
)

# `and wN, wN, #0xfffffffb` (bitmask immediate), register in bits 0-9.
AND_MASK_OP = 0x121D7800
AND_MASK_KEEP = 0xFFFFFC00
# `cmp wN, #2`
CMP_IMM2_OP = 0x7100001F
CMP_IMM2_KEEP = 0xFFC0001F
# `b.ne`
B_NE_OP = 0x54000001
B_NE_KEEP = 0xFF00001F
# `cmp xN, xM`
CMP_REG_OP = 0xEB00001F
CMP_REG_KEEP = 0xFFE0001F
# `b.hs`
B_HS_OP = 0x54000002
B_HS_KEEP = 0xFF00001F


def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]


def u64(data, off):
    return struct.unpack_from("<Q", data, off)[0]


def sext(value, bits):
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def adrp(insn, pc):
    if insn & 0x9F000000 != 0x90000000:
        raise ValueError("not adrp")
    imm = ((insn >> 29) & 3) | (((insn >> 5) & 0x7FFFF) << 2)
    if imm & (1 << 20):
        imm -= 1 << 21
    return (pc & ~0xFFF) + (imm << 12), insn & 31


def branch_target(pc, insn):
    if insn & 0xFC000000 not in (0x94000000, 0x14000000):
        return None
    return pc + sext(insn & 0x03FFFFFF, 26) * 4


def bcond_target(pc, insn):
    if insn & 0xFF000010 != 0x54000000:
        return None
    return pc + sext((insn >> 5) & 0x7FFFF, 19) * 4


def find_lk(path):
    data_full = Path(path).read_bytes()
    for start in fi.bss_candidates(data_full):
        try:
            base, end, bss_lo, bss_hi, label = fi.image_map(data_full[start:])
            return start, base, data_full[start:]
        except Exception:
            continue
    raise SystemExit("no valid LK slice")


def find_engine(data, base):
    hits = []
    n = len(ENGINE_PROLOGUE) * 4
    for off in range(0, len(data) - n, 4):
        if all(u32(data, off + k * 4) == w for k, w in enumerate(ENGINE_PROLOGUE)):
            hits.append(base + off)
    return hits


def find_context_page(data, base, engine):
    off = engine - base
    for j in range(off, min(off + 0x40, len(data) - 4), 4):
        w = u32(data, j)
        if w & 0x9F000000 == 0x90000000:
            page, _ = adrp(w, base + j)
            return page
    return None


def find_gate(data, base, engine):
    off = engine - base
    for j in range(off, min(off + 0x300, len(data) - 12), 4):
        w = u32(data, j)
        if w & AND_MASK_KEEP != AND_MASK_OP:
            continue
        if ((w >> 5) & 31) != (w & 31):
            continue
        w1 = u32(data, j + 4)
        w2 = u32(data, j + 8)
        if (w1 & CMP_IMM2_KEEP) != CMP_IMM2_OP or ((w1 >> 10) & 0xFFF) != 2:
            continue
        if (w2 & B_NE_KEEP) != B_NE_OP:
            continue
        skip = bcond_target(base + j + 8, w2)
        check_cmp = u32(data, j + 12) if j + 16 <= len(data) else None
        check_b = u32(data, j + 16) if j + 20 <= len(data) else None
        reject = None
        if check_b is not None and (check_b & B_HS_KEEP) == B_HS_OP:
            reject = bcond_target(base + j + 16, check_b)
        return {
            "gate": base + j,
            "skip": skip,
            "check_cmp": base + j + 12,
            "check_is_cmp_reg": check_cmp is not None and
                                (check_cmp & CMP_REG_KEEP) == CMP_REG_OP,
            "reject": reject,
        }
    return None


def find_setup(data, base, engine, ctx_page):
    """Nearest preceding pacibsp whose body stores to [ctx+0xf20] and [ctx+0xf28]."""
    off = engine - base
    stores = []
    reg_page = {}
    for j in range(max(0, off - 0x200), off, 4):
        w = u32(data, j)
        if w & 0x9F000000 == 0x90000000:
            page, rd = adrp(w, base + j)
            reg_page[rd] = page
            continue
        if w & 0xFFC00000 == 0xF9000000:  # str x, [xN, #imm]
            rn = (w >> 5) & 31
            imm = ((w >> 10) & 0xFFF) * 8
        elif w & 0xFFC00000 == 0xB9000000:  # str w, [xN, #imm]
            rn = (w >> 5) & 31
            imm = ((w >> 10) & 0xFFF) * 4
        else:
            continue
        if reg_page.get(rn) == ctx_page and imm in (0xF20, 0xF28):
            stores.append((base + j, imm))
    if not stores:
        return None, []
    first = min(s[0] for s in stores)
    fn = None
    for j in range(first - base, max(-1, first - base - 0x100), -4):
        if u32(data, j) == PACIBSP:
            fn = base + j
            break
    return fn, stores


def read_block_size(data, base, setup):
    off = setup - base
    for j in range(off, min(off + 0x40, len(data) - 8), 4):
        w = u32(data, j)
        if w & 0x9F000000 != 0x90000000:
            continue
        page, rd = adrp(w, base + j)
        w2 = u32(data, j + 4)
        if w2 & 0xFFC00000 != 0xF9400000:  # ldr x, [xN, #imm]
            continue
        if ((w2 >> 5) & 31) != rd:
            continue
        addr = page + ((w2 >> 10) & 0xFFF) * 8
        src = addr - base
        if 0 <= src <= len(data) - 8:
            return addr, u64(data, src)
    return None, None


def branch_xrefs(data, base, target):
    out = []
    for j in range(0, len(data) - 4, 4):
        tgt = branch_target(base + j, u32(data, j))
        if tgt == target:
            out.append((base + j, u32(data, j) & 0xFC000000))
    return out


def scan(path):
    off, base, data = find_lk(path)
    engines = find_engine(data, base)
    print(f"slice={off:#x} base={base:#x}")
    print(f"engines={[hex(x) for x in engines]}")
    if len(engines) != 1:
        print("expected exactly one engine prologue; stop")
        return
    engine = engines[0]
    ctx = find_context_page(data, base, engine)
    print(f"engine={engine:#x}")
    print(f"context_page={ctx:#x}" if ctx else "context_page=None")
    gate = find_gate(data, base, engine)
    if gate:
        print(f"flags_gate={gate['gate']:#x}  (and ~4 / cmp 2)")
        print(f"  skip_if_other_flags -> {gate['skip']:#x}")
        print(f"  checked_cmp={gate['check_cmp']:#x} is_cmp_reg={gate['check_is_cmp_reg']}")
        print(f"  reject_target={gate['reject']:#x}" if gate["reject"] else "  reject_target=None")
    else:
        print("flags_gate=None")
    setup, stores = find_setup(data, base, engine, ctx)
    print(f"setup={setup:#x}" if setup else "setup=None")
    for addr, imm in stores:
        print(f"  setup_store {addr:#x} -> slot +{imm:#x}")
    if setup:
        addr, value = read_block_size(data, base, setup)
        if addr is not None:
            print(f"block_size={value:#x} (from {addr:#x})")
        else:
            print("block_size=unresolved")
    print("engine callers:", [hex(a) for a, _ in branch_xrefs(data, base, engine)])
    if setup:
        print("setup callers:", [(hex(a), "BL" if op == 0x94000000 else "B")
                                 for a, op in branch_xrefs(data, base, setup)])


def main():
    ap = argparse.ArgumentParser(description="Odin data-plane bounds-check decoder")
    ap.add_argument("image")
    args = ap.parse_args()
    scan(args.image)


if __name__ == "__main__":
    main()
