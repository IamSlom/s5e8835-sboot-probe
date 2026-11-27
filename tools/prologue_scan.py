#!/usr/bin/env python3
"""Scan an sboot.bin LK slice for function prologue styles (PAC vs non-PAC).

Reports counts and sample addresses. Helps assess how PAC-built the LK is and
supports a future PAC-tolerant matcher. Static only.
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import firmware_inspect as fi

# little-endian instruction words
PACIBSP = 0xD503237F
AUTIBSP = 0xD50323FF
STP_X29_X30 = 0xA9807BFD  # stp x29, x30, [sp, #imm]! (mask below)
NONPAC_PROLOGUE = (0xA9BD7BFD, 0xA90157F6, 0xA9024FF4, 0x910003FD)


def scan(data):
    # find LK slice
    accepted = None
    for start in fi.bss_candidates(data):
        try:
            base, end, bss_lo, bss_hi, label = fi.image_map(data[start:])
            accepted = (start, base, end)
            break
        except Exception:
            continue
    if accepted is None:
        raise SystemExit("no valid LK slice")
    off, base, end = accepted
    lk = data[off:]
    n = len(lk) // 4

    pac = []
    nonpac = []
    for i in range(n):
        w = struct.unpack_from("<I", lk, i * 4)[0]
        addr = base + i * 4
        if w == PACIBSP:
            pac.append(addr)
        # non-PAC classic prologue: first word stp x29,x30,[sp,#-imm]!
        if w & 0xFFC07FFF == 0xA9807BFD or w == 0xA9BD7BFD:
            # check following words
            if i + 3 < n:
                ws = [struct.unpack_from("<I", lk, (i + j) * 4)[0] for j in range(4)]
                if tuple(ws) == NONPAC_PROLOGUE:
                    nonpac.append(addr)

    return off, base, end, pac, nonpac


def main():
    ap = argparse.ArgumentParser(description="Scan LK for PAC vs non-PAC prologues")
    ap.add_argument("image")
    args = ap.parse_args()
    data = Path(args.image).read_bytes()
    off, base, end, pac, nonpac = scan(data)
    print(f"slice={off:#x} base={base:#x} end={end:#x}")
    print(f"PAC prologues (pacibsp): {len(pac)}")
    print(f"non-PAC prologues (classic): {len(nonpac)}")
    print(f"sample PAC starts: {[hex(a) for a in pac[:10]]}")
    print(f"sample non-PAC starts: {[hex(a) for a in nonpac[:10]]}")


if __name__ == "__main__":
    main()
