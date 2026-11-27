#!/usr/bin/env python3
"""Derive screen_printf, cursor getter, and display update for s5e8835 LK.

The upstream screen_fns() heuristic is PAC-unaware and only matches a non-PAC
prologue that happens to occur once on these builds, yielding an address 4 bytes
past the real function start. This tool corrects for pacibsp and derives cursor
and display-update via call-frequency, then validates that each candidate is a
real function (pacibsp prologue). Static only.
"""
import argparse
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import firmware_inspect as fi

SVE = Path(r"C:\Users\Administrator\Documents\Default Project\sve-2026-3546\SVE-2026-3546-master")
sys.path.insert(0, str(SVE))
sys.path.insert(0, str(SVE / "signer"))
import resolve

PACIBSP = 0xD503237F


def bl_target(pc, w):
    imm = w & 0x03FFFFFF
    if imm & 0x02000000:
        imm -= 0x04000000
    return pc + imm * 4


def scan(path):
    data_full = Path(path).read_bytes()
    accepted = None
    for start in fi.bss_candidates(data_full):
        try:
            base, end, bss_lo, bss_hi, label = fi.image_map(data_full[start:])
            accepted = (start, base)
            break
        except Exception:
            continue
    if accepted is None:
        raise SystemExit("no valid LK slice")
    off, base = accepted
    data = data_full[off:]
    resolve.LK_BASE = base

    # locate screen_printf: the unique non-PAC prologue pattern, corrected to pacibsp
    pat = (0xA9BC7BFD, 0xA9015FFC, 0xA90257F6, 0xA9034FF4, 0x910003FD, 0xD11383FF)
    printf_stp = None
    for i in range(0, len(data) - 6 * 4, 4):
        ws = [resolve.u32(data, i + k * 4) for k in range(6)]
        if tuple(ws) == pat:
            printf_stp = i
            break
    if printf_stp is None:
        raise SystemExit("screen_printf prologue not found")
    # real start is pacibsp immediately before
    printf_addr = base + printf_stp
    if printf_stp - 4 >= 0 and resolve.u32(data, printf_stp - 4) == PACIBSP:
        printf_addr = base + printf_stp - 4

    # calls to printf
    calls = []
    for i in range(0, len(data) - 4, 4):
        w = resolve.u32(data, i)
        if (w & 0xFC000000) == 0x94000000:
            pc = base + i
            if bl_target(pc, w) == printf_addr:
                calls.append(i)

    cursors = Counter()
    for c in calls:
        for i in range(max(0, c - 0x40), c, 4):
            w = resolve.u32(data, i)
            if (w & 0xFC000000) == 0x94000000:
                pc = base + i
                cursors[bl_target(pc, w)] += 1

    updates = Counter()
    for c in calls:
        if c + 4 < len(data):
            w = resolve.u32(data, c + 4)
            if (w & 0xFC000000) == 0x94000000:
                pc = base + c + 4
                updates[bl_target(pc, w)] += 1

    # validate candidates are real functions (pacibsp prologue)
    def is_fn(addr):
        off = addr - base
        return off >= 0 and off + 4 <= len(data) and resolve.u32(data, off) == PACIBSP

    cursor = None
    if cursors:
        for addr, cnt in cursors.most_common():
            if is_fn(addr):
                cursor = addr
                break
    update = None
    if updates:
        for addr, cnt in updates.most_common():
            if is_fn(addr):
                update = addr
                break

    print(f"slice={off:#x} base={base:#x}")
    print(f"screen_printf = {printf_addr:#x} (calls={len(calls)})")
    print(f"cursor        = {cursor:#x} (freq={cursors.get(cursor,0)})" if cursor else "cursor = None")
    print(f"display_update= {update:#x} (freq={updates.get(update,0)})" if update else "display_update = None")
    print("top cursors:", [(hex(a), n) for a, n in cursors.most_common(3)])
    print("top updates:", [(hex(a), n) for a, n in updates.most_common(3)])


def main():
    ap = argparse.ArgumentParser(description="Derive screen printf/cursor/display-update")
    ap.add_argument("image")
    args = ap.parse_args()
    scan(args.image)


if __name__ == "__main__":
    main()
