import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from cmix_bit_trace_support import WRITER_CPP, inspect_log


class BitTraceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("clang++"), "requires a C++ compiler")
    def test_actual_writer_preserves_column_selection_bit_phase_and_probabilities(self):
        code = WRITER_CPP + r'''
int main() {
  float stage[28], hid[32], lhid[32], tf[4]; unsigned int zone = 1;
  for (int i=0;i<17;++i) {
    for (int j=0;j<28;++j) stage[j] = 100*i+j;
    for (int j=0;j<32;++j) { hid[j] = i+j*0.25f; lhid[j] = -hid[j]; }
    for (int j=0;j<4;++j) tf[j] = i+j;
    int override_active = i%3 == 0;
    hutter_bit_trace::writer.Prepare(i, 12000+i, stage, 28, i+0.5f,
                                    override_active, tf, 4, hid, lhid, &zone);
    hutter_bit_trace::writer.Observe(i%2, 12000+i+(override_active ? 0 : 10));
  }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe.cpp").write_text(code)
            subprocess.run(["clang++", "-std=c++17", "-O2", str(root / "probe.cpp"),
                            "-o", str(root / "probe")], check=True, capture_output=True)
            result = subprocess.run([str(root / "probe")], cwd=root, check=True,
                                    capture_output=True, text=True)
            log = root / "probe.log"
            log.write_text(result.stderr)
            report = inspect_log(log, root)
            self.assertEqual((report["bits"], report["channels"], report["one_bits"], report["overrides"]),
                             (17, 3, 8, 6))
            names = json.loads(result.stderr.split("CMIX_BITL_TRACE ")[1])
            trace = root / names["trace"]
            for i, row in enumerate(struct.iter_unpack("<HBB14f", trace.read_bytes()[28:])):
                self.assertEqual(row[:4], (12000+i, int(i%3 == 0) | ((i%2) << 1), 0, i+0.5))
                self.assertEqual(row[4:], tuple(100*i+j for j in (*range(7), *range(21, 27))))
            for k, row in enumerate(struct.iter_unpack("<69f", (root / names["channel"]).read_bytes()[28:])):
                i = k*8
                self.assertEqual(row[:4], tuple(i+j for j in range(4)))
                self.assertEqual(row[4:36], tuple(i+j*0.25 for j in range(32)))
                self.assertEqual(row[36:68], tuple(-(i+j*0.25) for j in range(32)))
                self.assertEqual(row[68], 1)
            original = trace.read_bytes()
            corrupted = bytearray(original)
            corrupted[31] = 1  # reserved byte of first record
            trace.write_bytes(corrupted)
            with self.assertRaisesRegex(ValueError, "trace values"):
                inspect_log(log, root)
            trace.write_bytes(original[:-1])
            with self.assertRaisesRegex(ValueError, "length"):
                inspect_log(log, root)
            trace.write_bytes(original)
            log.write_text(result.stderr + result.stderr)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                inspect_log(log, root)
