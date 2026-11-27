import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import odin_scan as od


class TestDecoderHelpers(unittest.TestCase):
    def test_adrp_page(self):
        # adrp x22, #0xf4c9b000 at 0xf4864160 (October engine)
        page, reg = od.adrp(0xF00021B6, 0xF4864160)
        self.assertEqual(page, 0xF4C9B000)
        self.assertEqual(reg, 22)

    def test_bne_target(self):
        # b.ne at 0xf48641c4 -> 0xf48643d4 (October skip target)
        self.assertEqual(od.bcond_target(0xF48641C4, 0x54001081), 0xF48643D4)
        # same encoding on EZJ2 -> 0xf4864654
        self.assertEqual(od.bcond_target(0xF4864444, 0x54001081), 0xF4864654)

    def test_bhs_target(self):
        # b.hs at 0xf48641cc -> 0xf4864474 (October reject target)
        self.assertEqual(od.bcond_target(0xF48641CC, 0x54001542), 0xF4864474)

    def test_bl_target(self):
        # bl at 0xf480fff0 -> engine 0xf4864140
        self.assertEqual(od.branch_target(0xF480FFF0, 0x94015054), 0xF4864140)

    def test_gate_masks(self):
        self.assertEqual(0x121D794A & od.AND_MASK_KEEP, od.AND_MASK_OP)
        self.assertEqual(0x7100095F & od.CMP_IMM2_KEEP, od.CMP_IMM2_OP)
        self.assertEqual(0xEB09011F & od.CMP_REG_KEEP, od.CMP_REG_OP)


class TestGateDecode(unittest.TestCase):
    def test_gate_sequence(self):
        words = [0x121D794A,  # and w10, w10, #0xfffffffb
                 0x7100095F,  # cmp w10, #2
                 0x54001081,  # b.ne skip
                 0xEB09011F,  # cmp x8, x9
                 0x54001542]  # b.hs reject
        data = bytearray(0x40)
        for k, w in enumerate(words):
            struct.pack_into("<I", data, k * 4, w)
        gate = od.find_gate(bytes(data), 0, 0)
        self.assertIsNotNone(gate)
        self.assertEqual(gate["gate"], 0)
        self.assertEqual(gate["skip"], od.bcond_target(8, 0x54001081))
        self.assertEqual(gate["check_cmp"], 12)
        self.assertTrue(gate["check_is_cmp_reg"])
        self.assertEqual(gate["reject"], od.bcond_target(16, 0x54001542))


class TestEngineLocate(unittest.TestCase):
    def test_engine_prologue(self):
        data = bytearray(0x400)
        off = 0x100
        for k, w in enumerate(od.ENGINE_PROLOGUE):
            struct.pack_into("<I", data, off + k * 4, w)
        self.assertEqual(od.find_engine(bytes(data), 0xF4800000), [0xF4800100])


class TestCLI(unittest.TestCase):
    def test_runs_on_minimal(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.bin"
            p.write_bytes(b"\x00" * 0x2000)
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "odin_scan.py"), str(p)],
                               capture_output=True, text=True)
            self.assertIn(r.returncode, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
