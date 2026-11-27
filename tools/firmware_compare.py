#!/usr/bin/env python3
"""Compare two Samsung sboot.bin images offline.

Reports structural differences: LK slice, base/end, BSS, markers, embedded ELF
counts, and per-slice SHA-256. Static only.
"""
import argparse
import hashlib
import json
from pathlib import Path

import firmware_inspect as fi


def snapshot(path):
    data = Path(path).read_bytes()
    markers = fi.find_markers(data)
    cands = fi.bss_candidates(data)
    accepted = None
    for start in cands:
        try:
            base, end, bss_lo, bss_hi, label = fi.image_map(data[start:])
            accepted = {
                "slice_offset": start,
                "base": base,
                "end": end,
                "bss_start": bss_lo,
                "bss_end": bss_hi,
                "map_label": label,
                "slice_sha256": hashlib.sha256(data[start:]).hexdigest(),
                "slice_size": len(data) - start,
            }
            break
        except Exception as e:
            accepted = {"slice_offset": start, "rejected": str(e)}
    elfs = fi.find_elfs(data)
    return {
        "file": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "markers": [hex(m) for m in markers],
        "bss_candidates": [hex(c) for c in cands],
        "lk": accepted,
        "embedded_elf_count": len(elfs),
        "embedded_elf_offsets": [hex(e["offset"]) for e in elfs],
    }


def compare(a, b):
    sa, sb = snapshot(a), snapshot(b)
    rows = []
    rows.append(("file size", hex(sa["size"]), hex(sb["size"]), sa["size"] == sb["size"]))
    rows.append(("sha256", sa["sha256"][:16] + "...", sb["sha256"][:16] + "...", sa["sha256"] == sb["sha256"]))
    rows.append(("s5e8835 markers", str(sa["markers"]), str(sb["markers"]), sa["markers"] == sb["markers"]))
    rows.append(("BSS candidates", str(sa["bss_candidates"]), str(sb["bss_candidates"]), sa["bss_candidates"] == sb["bss_candidates"]))
    la, lb = sa["lk"], sb["lk"]
    if isinstance(la, dict) and isinstance(lb, dict):
        for key in ("slice_offset", "base", "end", "bss_start", "bss_end", "slice_sha256"):
            va = la.get(key); vb = lb.get(key)
            rows.append((f"lk.{key}", hex(va) if isinstance(va, int) else va, hex(vb) if isinstance(vb, int) else vb, va == vb))
    rows.append(("embedded ELF count", sa["embedded_elf_count"], sb["embedded_elf_count"], sa["embedded_elf_count"] == sb["embedded_elf_count"]))
    return sa, sb, rows


def main():
    ap = argparse.ArgumentParser(description="Compare two sboot.bin images")
    ap.add_argument("image_a")
    ap.add_argument("image_b")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sa, sb, rows = compare(args.image_a, args.image_b)
    if args.json:
        print(json.dumps({"a": sa, "b": sb, "rows": [{"field": r[0], "a": r[1], "b": r[2], "same": r[3]} for r in rows]}, indent=2))
        return
    print(f"A: {sa['file']}")
    print(f"B: {sb['file']}")
    print()
    w = max(len(r[0]) for r in rows)
    for field, va, vb, same in rows:
        flag = "SAME" if same else "DIFF"
        print(f"{field:<{w}}  A={va}  B={vb}  [{flag}]")


if __name__ == "__main__":
    main()
