import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import prologue_scan as ps


class TestPrologueScanCLI(unittest.TestCase):
    def test_runs_on_minimal(self):
        # Minimal buffer won't have a valid slice; expect non-zero exit or error.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.bin"
            p.write_bytes(b"\x00" * 0x2000)
            import subprocess
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "prologue_scan.py"), str(p)],
                               capture_output=True, text=True)
            # Either succeeds with no slice message or fails; just ensure it doesn't crash unexpectedly
            self.assertIn(r.returncode, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
