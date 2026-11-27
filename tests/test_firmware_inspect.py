import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import firmware_inspect as fi


class TestMarkers(unittest.TestCase):
    def test_find_markers_basic(self):
        data = b"\x00" * 10 + b"s5e8835" + b"\x00" * 5 + b"s5e8835"
        self.assertEqual(fi.find_markers(data), [10, 22])

    def test_find_markers_absent(self):
        self.assertEqual(fi.find_markers(b"hello world"), [])


class TestBssCandidates(unittest.TestCase):
    def _make(self):
        # Build a minimal buffer with a BSS triple at page-aligned-ish offset
        buf = bytearray(0x2000)
        bss_start = 0xF4C44000
        bss_end = 0xF5087270
        # place triple at offset 0x30 within a 0x1000 page (off % 0x1000 < 0x400)
        off = 0x1030
        struct.pack_into("<QQQ", buf, off, bss_start, bss_start, bss_end)
        return bytes(buf), off

    def test_candidate_found(self):
        data, off = self._make()
        cands = fi.bss_candidates(data)
        self.assertIn(off & ~0xFFF, cands)


class TestImageMap(unittest.TestCase):
    def _make_slice(self):
        # Replicate resolve.image_map expectations: BSS triple + one mapping containing BSS.
        bss_start = 0xF4C44000
        bss_end = 0xF4C45000
        base = 0xF4800000
        end = 0xF6000000
        buf = bytearray(0x4000)
        # BSS triple at 0x30
        struct.pack_into("<QQQ", buf, 0x30, bss_start, bss_start, bss_end)
        # mapping struct: name(8) start(8) end(8) physical(8) extra(8) at some offset
        name_str = b"RAM\x00"
        name_off = 0x100
        buf[name_off:name_off + len(name_str)] = name_str
        name_addr = base + name_off
        map_off = 0x200
        struct.pack_into("<5Q", buf, map_off, name_addr, base, end, base, 0)
        return bytes(buf), base, end, bss_start, bss_end

    def test_image_map_valid(self):
        data, base, end, bs, be = self._make_slice()
        b, e, lo, hi, label = fi.image_map(data)
        self.assertEqual(b, base)
        self.assertEqual(e, end)
        self.assertEqual(lo, bs)
        self.assertEqual(hi, be)
        self.assertEqual(label, "RAM")

    def test_image_map_rejects_no_triple(self):
        data = b"\x00" * 0x1000
        with self.assertRaises(ValueError):
            fi.image_map(data)


class TestElfParse(unittest.TestCase):
    def _minimal_elf64(self):
        # ELF64 little-endian ET_DYN AArch64
        import struct as s
        buf = bytearray(64)
        buf[0:4] = b"\x7fELF"
        buf[4] = 2  # 64-bit
        buf[5] = 1  # little
        buf[6] = 1  # version
        # e_type at 16
        s.pack_into("<H", buf, 16, 3)  # ET_DYN
        s.pack_into("<H", buf, 18, 183)  # AArch64
        s.pack_into("<Q", buf, 24, 0x42c4)  # entry
        # rest zeros fine
        return bytes(buf)

    def test_parse_elf64(self):
        e = fi.parse_elf(self._minimal_elf64())
        self.assertIsNotNone(e)
        self.assertEqual(e["class"], "ELF64")
        self.assertEqual(e["type"], "DYN")
        self.assertEqual(e["machine"], "AArch64")
        self.assertEqual(e["entry"], 0x42C4)

    def test_parse_elf_rejects_garbage(self):
        self.assertIsNone(fi.parse_elf(b"not an elf" + b"\x00" * 64))

    def test_find_elfs(self):
        data = b"\x00" * 100 + self._minimal_elf64() + b"\x00" * 100
        elfs = fi.find_elfs(data)
        self.assertEqual(len(elfs), 1)
        self.assertEqual(elfs[0]["offset"], 100)


class TestInspectCLI(unittest.TestCase):
    def test_runs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.bin"
            p.write_bytes(b"\x00" * 0x2000)
            import subprocess
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "firmware_inspect.py"), str(p)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("file        :", r.stdout)


if __name__ == "__main__":
    unittest.main()
