#!/usr/bin/env python3
"""PAC-aware scanner for blk_bread / blk_bwrite wrapper functions.

The upstream named_fn() heuristic matches a non-PAC prologue word sequence that
can appear immediately after `pacibsp` on PAC-built LK, yielding an address 4
bytes past the real function start. This tool scans backward from each string
XREF to the nearest `pacibsp` (or classic non-PAC prologue) and reports the
true function start. Static only.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import firmware_inspect as fi

SVE = Path(r"C:\Users\Administrator\Documents\Default Project\sve-2026-3546\SVE-2026-3546-master")
sys.path.insert(0, str(SVE))
sys.path.insert(0, str(SVE / "signer"))
try:
    import resolve
except Exception as e:
    raise SystemExit(f"resolve.py unavailable: {e}")

PACIBSP = 0xD503237F
CLASSIC = [0xA9BD7BFD, 0xA90157F6, 0xA9024FF4, 0x910003FD]


def scan(path, names=(b"blk_bread", b"blk_bwrite")):
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
    result = {}
    for name in names:
        starts = set()
        try:
            refs = resolve.str_refs(data, name)
        except Exception as e:
            result[name.decode()] = {"error": str(e)}
            continue
        for ref, _, _ in refs:
            for j in range(ref, max(-1, ref - 0x1000), -4):
                if j < 0:
                    break
                if j + 12 <= len(data):
                    ws = [resolve.u32(data, j + k * 4) for k in range(4)]
                    if ws == CLASSIC:
                        # PAC-built functions have pacibsp immediately before
                        if j - 4 >= 0 and resolve.u32(data, j - 4) == PACIBSP:
                            starts.add(base + j - 4)
                        else:
                            starts.add(base + j)
                        break
                word = resolve.u32(data, j)
                if word == PACIBSP:
                    starts.add(base + j)
                    break
        result[name.decode()] = sorted(starts)
    return off, base, result


def main():
    ap = argparse.ArgumentParser(description="PAC-aware blk wrapper scanner")
    ap.add_argument("image")
    args = ap.parse_args()
    off, base, result = scan(args.image)
    print(f"slice={off:#x} base={base:#x}")
    for k, v in result.items():
        print(f"{k}: {[hex(x) for x in v]}")


if __name__ == "__main__":
    main()
