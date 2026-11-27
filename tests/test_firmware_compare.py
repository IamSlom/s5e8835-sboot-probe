import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import firmware_compare as fc


class TestSnapshot(unittest.TestCase):
    def test_snapshot_basic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.bin"
            p.write_bytes(b"\x00" * 0x2000)
            s = fc.snapshot(p)
            self.assertEqual(s["size"], 0x2000)
            self.assertIn("sha256", s)


class TestCompareCLI(unittest.TestCase):
    def test_runs(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.bin"; b = Path(td) / "b.bin"
            a.write_bytes(b"\x00" * 0x2000); b.write_bytes(b"\x01" * 0x2000)
            import subprocess
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "firmware_compare.py"), str(a), str(b)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("A:", r.stdout)


if __name__ == "__main__":
    unittest.main()
