#!/usr/bin/env python3
"""Offline firmware inspection utility for Samsung sboot.bin images.

Reads a local firmware file and reports binary metadata, markers, LK slice
candidates, BSS descriptors, image mapping, and any embedded ELF objects.

Static only: never opens a device, never writes firmware.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path


PAGE_SIZE = 0x1000


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path):
    import hashlib as _h
    h = _h.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_markers(data, needle=b"s5e8835"):
    out = []
    start = 0
    while True:
        i = data.find(needle, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out


def bss_candidates(data):
    out = set()
    for off in range(0, len(data) - 0x18, 4):
        try:
            s, dup, e = struct.unpack_from("<QQQ", data, off)
        except struct.error:
            break
        if (s == dup and 0x80000000 <= s < 0x1000000000
                and s % 0x1000 == 0 and s < e < s + 0x10000000
                and off % 0x1000 < 0x400):
            out.add(off & ~0xFFF)
    return sorted(out)


def image_map(data):
    """Replicate resolve.image_map(): validate BSS triple + single mapping."""
    bss = []
    limit = min(len(data), 0x400)
    for offset in range(0, limit - 0x18 + 1, 8):
        try:
            start, duplicate, end = struct.unpack_from("<QQQ", data, offset)
        except struct.error:
            break
        if (start == duplicate and 0x80000000 <= start < 0x1000000000 and
                start % PAGE_SIZE == 0 and start < end and
                end - start < 0x10000000):
            bss.append((start, end))
    if len(bss) != 1:
        raise ValueError(f"LK BSS: {bss}")

    bss_start, bss_end = bss[0]
    mappings = []
    for offset in range(0, len(data) - 0x28, 8):
        try:
            name, start, end, physical, _ = struct.unpack_from("<5Q", data, offset)
        except struct.error:
            break
        if (start != physical or start % 0x100000 or
                not start <= bss_start < bss_end <= end or
                not 0 < bss_start - start < 0x1000000):
            continue
        name_offset = name - start
        if not 0 <= name_offset < len(data):
            continue
        name_end = data.find(b"\0", name_offset, min(len(data), name_offset + 0x80))
        if name_end < 0:
            continue
        label = data[name_offset:name_end]
        if label and all(0x20 <= v < 0x7F for v in label):
            mappings.append((start, end, label.decode("ascii", "replace")))
    mappings = sorted(set(mappings))
    if len(mappings) != 1:
        raise ValueError(f"LK map: {mappings}")
    return mappings[0][0], mappings[0][1], bss_start, bss_end, mappings[0][2]


def parse_elf(data, base_offset=0):
    """Parse an ELF64/ELF32 header at data[0:]. Returns dict or None."""
    if len(data) < 52 or data[:4] != b"\x7fELF":
        return None
    ei_class = data[4]
    ei_data = data[5]
    if ei_class not in (1, 2):
        return None
    endian = "<" if ei_data == 1 else ">"
    is64 = ei_class == 2
    try:
        if is64:
            e_type, e_machine = struct.unpack_from(endian + "HH", data, 16)
            e_entry = struct.unpack_from(endian + "Q", data, 24)[0]
            e_phoff = struct.unpack_from(endian + "Q", data, 32)[0]
            e_shoff = struct.unpack_from(endian + "Q", data, 40)[0]
            e_flags = struct.unpack_from(endian + "I", data, 48)[0]
            e_ehsize = struct.unpack_from(endian + "H", data, 52)[0]
            e_phentsize = struct.unpack_from(endian + "H", data, 54)[0]
            e_phnum = struct.unpack_from(endian + "H", data, 56)[0]
            e_shentsize = struct.unpack_from(endian + "H", data, 58)[0]
            e_shnum = struct.unpack_from(endian + "H", data, 60)[0]
            e_shstrndx = struct.unpack_from(endian + "H", data, 62)[0]
        else:
            e_type, e_machine = struct.unpack_from(endian + "HH", data, 16)
            e_entry = struct.unpack_from(endian + "I", data, 24)[0]
            e_phoff = struct.unpack_from(endian + "I", data, 28)[0]
            e_shoff = struct.unpack_from(endian + "I", data, 32)[0]
            e_flags = struct.unpack_from(endian + "I", data, 36)[0]
            e_ehsize = struct.unpack_from(endian + "H", data, 40)[0]
            e_phentsize = struct.unpack_from(endian + "H", data, 42)[0]
            e_phnum = struct.unpack_from(endian + "H", data, 44)[0]
            e_shentsize = struct.unpack_from(endian + "H", data, 46)[0]
            e_shnum = struct.unpack_from(endian + "H", data, 48)[0]
            e_shstrndx = struct.unpack_from(endian + "H", data, 50)[0]
    except struct.error:
        return None

    machine_names = {183: "AArch64", 62: "x86-64", 3: "x86", 40: "ARM"}
    type_names = {1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
    result = {
        "offset": base_offset,
        "class": "ELF64" if is64 else "ELF32",
        "endian": "little" if ei_data == 1 else "big",
        "type": type_names.get(e_type, str(e_type)),
        "machine": machine_names.get(e_machine, str(e_machine)),
        "entry": e_entry,
        "phoff": e_phoff,
        "shoff": e_shoff,
        "phnum": e_phnum,
        "shnum": e_shnum,
        "shstrndx": e_shstrndx,
        "flags": e_flags,
    }

    # Section names if available
    sections = []
    if e_shoff and e_shnum and e_shstrndx < e_shnum:
        try:
            # read shstrtab
            if is64:
                strtab_off = struct.unpack_from(endian + "Q", data, e_shoff + e_shstrndx * e_shentsize + 24)[0]
            else:
                strtab_off = struct.unpack_from(endian + "I", data, e_shoff + e_shstrndx * e_shentsize + 16)[0]
            for i in range(e_shnum):
                soff = e_shoff + i * e_shentsize
                if is64:
                    sh_name = struct.unpack_from(endian + "I", data, soff)[0]
                    sh_type = struct.unpack_from(endian + "I", data, soff + 4)[0]
                    sh_addr = struct.unpack_from(endian + "Q", data, soff + 16)[0]
                    sh_size = struct.unpack_from(endian + "Q", data, soff + 32)[0]
                else:
                    sh_name = struct.unpack_from(endian + "I", data, soff)[0]
                    sh_type = struct.unpack_from(endian + "I", data, soff + 4)[0]
                    sh_addr = struct.unpack_from(endian + "I", data, soff + 12)[0]
                    sh_size = struct.unpack_from(endian + "I", data, soff + 20)[0]
                name = ""
                if strtab_off and sh_name:
                    endn = data.find(b"\0", strtab_off + sh_name)
                    name = data[strtab_off + sh_name:endn].decode("ascii", "replace")
                sections.append({"name": name, "type": sh_type, "addr": sh_addr, "size": sh_size})
            result["sections"] = sections
        except Exception:
            pass
    return result


def find_elfs(data):
    out = []
    idx = 0
    while True:
        i = data.find(b"\x7fELF", idx)
        if i < 0:
            break
        # parse a copy starting at i
        elf = parse_elf(data[i:], base_offset=i)
        if elf is not None:
            out.append(elf)
        idx = i + 1
    return out


def inspect(path, as_json=False):
    data = Path(path).read_bytes()
    markers = find_markers(data)
    cands = bss_candidates(data)
    slices = []
    for start in cands:
        try:
            base, end, bss_lo, bss_hi, label = image_map(data[start:])
            slices.append({
                "offset": start,
                "base": base,
                "end": end,
                "bss_start": bss_lo,
                "bss_end": bss_hi,
                "map_label": label,
            })
        except Exception as e:
            slices.append({"offset": start, "rejected": str(e)})

    elfs = find_elfs(data)

    report = {
        "file": str(path),
        "size": len(data),
        "size_hex": hex(len(data)),
        "sha256": sha256_file(path),
        "md5": md5_file(path),
        "s5e8835_markers": [hex(m) for m in markers],
        "bss_slice_candidates": [hex(c) for c in cands],
        "lk_slices": slices,
        "embedded_elfs": elfs,
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return report

    print(f"file        : {path}")
    print(f"size        : {len(data)} ({len(data):#x})")
    print(f"sha256      : {report['sha256']}")
    print(f"md5         : {report['md5']}")
    print(f"s5e8835 markers: {[hex(m) for m in markers]}")
    print(f"BSS-triple slice candidates: {[hex(c) for c in cands]}")
    for sl in slices:
        if "rejected" in sl:
            print(f"  reject {sl['offset']:#x}: {sl['rejected']}")
        else:
            print(f"  slice={sl['offset']:#x} base={sl['base']:#x} end={sl['end']:#x} "
                  f"bss=[{sl['bss_start']:#x},{sl['bss_end']:#x}) label={sl['map_label']}")
    print(f"embedded ELF objects: {len(elfs)}")
    for e in elfs:
        print(f"  off={e['offset']:#x} {e['class']} {e['type']} machine={e['machine']} "
              f"entry={e['entry']:#x} sections={e['shnum']}")
        for s in e.get("sections", [])[:12]:
            if s["name"]:
                print(f"     section {s['name']}: addr={s['addr']:#x} size={s['size']:#x}")
    return report


def main():
    ap = argparse.ArgumentParser(description="Offline firmware inspection for sboot.bin")
    ap.add_argument("image", type=Path)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()
    inspect(args.image, as_json=args.json)


if __name__ == "__main__":
    main()
