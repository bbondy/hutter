import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cmix_activity_support import COUNTER_CPP, parse_log


class ActivationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("clang++"), "requires a C++ compiler")
    def test_actual_counter_block_records_sparse_zero_calls_and_moments(self):
        code = COUNTER_CPP + r'''
int main() {
  uint8_t q[3] = {2,0,127}; uint16_t idx[2] = {0,2};
  for (int l=0;l<16;++l) {
    hutter_mlp_activity::counters.Record(l,3,q,idx,2);
    hutter_mlp_activity::counters.Record(l,3,q,idx,0);
  }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe.cpp").write_text(code)
            subprocess.run(["clang++", "-std=c++17", "-O2", str(root / "probe.cpp"), "-o", str(root / "probe")], check=True, capture_output=True)
            result = subprocess.run([str(root / "probe")], check=True, capture_output=True, text=True)
            log = root / "probe.log"
            log.write_text(result.stderr)
            rows = parse_log(log)
            for row in rows:
                self.assertEqual(row["calls"], 2)
                self.assertEqual(row["count"], [1, 0, 1])
                self.assertEqual(row["sum"], [2, 0, 127])
                self.assertEqual(row["sumsq"], [4, 0, 16129])
            rows[0]["sumsq"][0] = 3
            log.write_text("".join("CMIX_MLP_ACTIVITY " + json.dumps(r) + "\n" for r in rows))
            with self.assertRaisesRegex(ValueError, "moments"):
                parse_log(log)
            log.write_text(result.stderr + result.stderr)
            with self.assertRaisesRegex(ValueError, "layers"):
                parse_log(log)
