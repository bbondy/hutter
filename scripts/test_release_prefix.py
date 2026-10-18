from pathlib import Path
import sys
import tempfile
import unittest

from release_prefix import capture_prefix


class ReleasePrefixTests(unittest.TestCase):
    def test_snapshot_terminates_the_owned_writer_without_finishing_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            code = "from pathlib import Path; import time; Path('payload').write_bytes(b'abcd'*100); time.sleep(20)"
            result = capture_prefix([sys.executable, "-c", code], work, work / "payload", 101, 5)
            self.assertEqual(result["status"], "prefix_captured")
            self.assertFalse(result["complete_archive"])
            self.assertEqual((work / "coder-prefix.bin").read_bytes(), (b"abcd" * 100)[:101])
            self.assertLess(result["exit_code"], 0)

    def test_timeout_and_early_exit_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            timeout = capture_prefix([sys.executable, "-c", "import time; time.sleep(20)"],
                                     work, work / "missing", 100, 0.1)
            self.assertEqual(timeout["status"], "timeout")
            exited = capture_prefix([sys.executable, "-c", "raise SystemExit(2)"],
                                    work, work / "missing", 100, 5)
            self.assertEqual(exited["status"], "exited_before_capture")
            self.assertEqual(exited["exit_code"], 2)

    def test_rejects_metadata_only_and_marker_without_sufficient_later_output(self):
        for marker in ("", "print('main text',flush=True);"):
            with tempfile.TemporaryDirectory() as folder:
                work = Path(folder)
                code = "from pathlib import Path; import time; Path('payload').write_bytes(b'x'*200); " + marker + "time.sleep(10)"
                result = capture_prefix([sys.executable, "-c", code], work, work / "payload",
                                        100, 5, "main text", 10)
                self.assertEqual(result["status"], "insufficient_phase_coverage")
                self.assertFalse((work / "coder-prefix.bin").exists())

    def test_accepts_output_beyond_a_previously_observed_phase_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            code = ("from pathlib import Path; import time; Path('payload').write_bytes(b'x'*10); "
                    "print('main text',flush=True); time.sleep(.6); "
                    "Path('payload').write_bytes(b'x'*200); time.sleep(10)")
            result = capture_prefix([sys.executable, "-c", code], work, work / "payload",
                                    100, 5, "main text", 20)
            self.assertEqual(result["status"], "prefix_captured")
            self.assertEqual(result["required_phase_observed"]["output_bytes_when_observed"], 10)


if __name__ == "__main__":
    unittest.main()
