import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from bitl_replay import rewrite_verifier
from cmix_bit_trace_support import TRACE_HEADER, CHANNEL_HEADER
from competitive import ENGINE


class ReplayVerifierTests(unittest.TestCase):
    def test_patch_requires_exact_anchors(self):
        source = (ENGINE / "training/bitl/trainer/replay_trainer.cpp").read_text()
        changed = rewrite_verifier(source)
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            rewrite_verifier(changed)
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            rewrite_verifier(source.replace("      if (!meta_skip) bit_head::Observe(bit);", ""))

    @unittest.skipUnless(shutil.which("clang++"), "requires a C++ compiler")
    def test_actual_driver_accepts_equal_probabilities_and_rejects_mismatch_and_extra_data(self):
        stub = r'''
#include "bit_head.h"
namespace bit_head {
bool Init() { return true; }
void Shutdown() {}
void Observe(int) {}
void SetAux(const float*,int) {}
void SetTf(const float*,int) {}
void SetLhid(const float*,int,int) {}
void SetZone(const unsigned int*) {}
int Cells() { return 16; }
int NumParams() { return 3585; }
int NumInputs() { return 90; }
int Wlen() { return 1024; }
unsigned int Adjust(unsigned int p,const float*,int,float,int o) { return o ? p : p+1; }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = ENGINE / "training/bitl/trainer"
            (root / "driver.cpp").write_text(rewrite_verifier((upstream / "replay_trainer.cpp").read_text()))
            shutil.copy2(upstream / "bit_head.h", root / "bit_head.h")
            (root / "stub.cpp").write_text(stub)
            subprocess.run(["clang++", "-std=c++17", "-O2", str(root / "driver.cpp"),
                            str(root / "stub.cpp"), "-o", str(root / "probe")], check=True, capture_output=True)
            trace = TRACE_HEADER + b"".join(struct.pack("<HBB14f", 10000+i, 2*(i%2), 0, *([0.0]*14)) for i in range(17))
            (root / "trace.bin").write_bytes(trace)
            (root / "channel.bin").write_bytes(CHANNEL_HEADER + bytes(276*3))
            probability = b"".join(struct.pack("<H", 10001+i) for i in range(17))
            path = root / "prob.bin"
            env = {**os.environ, "REPLAY_CHANNEL": str(root / "channel.bin"), "HUTTER_EXPECT_PROBABILITIES": str(path)}

            def run(data):
                path.write_bytes(data)
                return subprocess.run([str(root / "probe"), str(root / "trace.bin"), "0", "0"],
                                      cwd=root, env=env, capture_output=True, text=True)

            result = run(probability)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stderr.split("CMIX_BITL_REPLAY ")[1]),
                             {"bits": 17, "integer_probabilities_equal": True})
            result = run(probability[:4] + struct.pack("<H", 12345) + probability[6:])
            self.assertEqual(result.returncode, 6)
            self.assertIn("mismatch at bit 2: live=12345 replay=10003", result.stderr)
            self.assertEqual(run(probability + b"\0").returncode, 5)
            self.assertEqual(run(probability[:-2]).returncode, 5)
