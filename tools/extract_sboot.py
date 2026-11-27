#!/usr/bin/env python3
"""Extract and decompress sboot.bin from a Samsung BL *.tar.md5 package.

Offline: reads a local BL tar, extracts sboot.bin.lz4, decompresses with lz4,
writes sboot.bin next to the input (or a chosen path), and prints its hash.
Requires the `lz4` Python module. Static only.
"""
import argparse
import hashlib
import os
import sys
import tarfile
from pathlib import Path

try:
    import lz4.frame
except ImportError as e:  # pragma: no cover
    print("lz4 module not available:", e, file=sys.stderr)
    sys.exit(2)


def extract(bl_path, member="sboot.bin.lz4", out_path=None, expected_sha256=None):
    bl_path = Path(bl_path)
    with tarfile.open(bl_path) as tf:
        names = tf.getnames()
        if member not in names:
            raise SystemExit(f"{member} not found in {bl_path}; members: {names}")
        raw = tf.extractfile(member).read()
    dec = lz4.frame.decompress(raw)
    if out_path is None:
        out_path = bl_path.with_name("sboot.bin")
    out_path = Path(out_path)
    out_path.write_bytes(dec)
    h = hashlib.sha256(dec).hexdigest()
    print(f"extracted {member} -> {out_path}")
    print(f"size   : {len(dec):#x}")
    print(f"sha256 : {h}")
    if expected_sha256 and h != expected_sha256:
        print(f"WARNING: hash mismatch (expected {expected_sha256})", file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="Extract sboot.bin from a BL tar.md5")
    ap.add_argument("bl", type=Path, help="BL *.tar.md5 path")
    ap.add_argument("--member", default="sboot.bin.lz4")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--expect-sha256", default=None)
    args = ap.parse_args()
    sys.exit(extract(args.bl, args.member, args.out, args.expect_sha256))


if __name__ == "__main__":
    main()
