import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from release_full import execute, file_record, run_phase, sample_resources


LIMITS = {"phase_timeout_seconds": 5, "sample_seconds": 0.02,
          "rss_stop_bytes": 1000, "scratch_stop_bytes": 1000,
          "minimum_free_bytes": 100}


def ample_resources(pid, work):
    return {"process_tree_rss_bytes": 50, "apparent_regular_file_bytes": 70,
            "allocated_regular_file_bytes": 80, "work_free_bytes": 10000,
            "tmp_free_bytes": 10000}


class FullReleaseTests(unittest.TestCase):
    def test_success_and_failure_are_persisted(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            for code in (0, 7):
                result = run_phase([sys.executable, "-c", f"raise SystemExit({code})"],
                                   work, LIMITS, ample_resources)
                saved = json.loads((work / "phase.json").read_text())
                self.assertEqual(saved, result)
                self.assertEqual(saved["exit_code"], code)
                self.assertEqual(saved["status"], "ok" if code == 0 else "failed")
                self.assertIn("run.log_sha256", saved)

    def test_timeout_and_resource_stops_are_failures(self):
        cases = [("timeout", {"phase_timeout_seconds": 0.05}, {}),
                 ("sampled_rss_limit", {}, {"process_tree_rss_bytes": 1001}),
                 ("sampled_scratch_limit", {}, {"apparent_regular_file_bytes": 1001}),
                 ("low_disk_space", {}, {"tmp_free_bytes": 99})]
        for expected, limits, sample in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                result = run_phase([sys.executable, "-c", "import time; time.sleep(10)"],
                                   Path(folder), {**LIMITS, **limits},
                                   lambda pid, work: {**ample_resources(pid, work), **sample})
                self.assertEqual(result["status"], expected)
                self.assertLess(result["exit_code"], 0)
                self.assertLess(result["wall_seconds"], 5)

    def test_successful_parent_does_not_leave_owned_children_running(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            child = "import time; from pathlib import Path; time.sleep(.25); Path('leaked').touch()"
            parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
            result = run_phase([sys.executable, "-c", parent], work, LIMITS, ample_resources)
            self.assertEqual(result["status"], "ok")
            time.sleep(0.35)
            self.assertFalse((work / "leaked").exists())

    def test_full_result_requires_original_bytes_and_published_archive(self):
        # Stub expensive native execution; exercise actual copy, hashing,
        # independent-directory setup, score accounting and final acceptance.
        original_read = Path.read_text

        def host_text(path, *args, **kwargs):
            if str(path) == "/proc/cpuinfo":
                return "flags : avx2 fma"
            if str(path) == "/proc/meminfo":
                return "test host"
            return original_read(path, *args, **kwargs)

        for wrong_restore, wrong_archive in ((False, False), (True, False), (False, True)):
            with self.subTest(wrong_restore=wrong_restore, wrong_archive=wrong_archive), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                corpus, binary, archive = root / "input", root / "binary", root / "expected-archive"
                corpus.write_bytes(b"original bytes")
                binary.write_bytes(b"fake compressor")
                archive.write_bytes(b"fake archive")
                frozen = {"compressor": file_record(binary), "weights_sha256": "weights",
                          "expected_archive": file_record(archive)}
                if wrong_archive:
                    frozen["expected_archive"]["sha256"] = "wrong"
                protocol = {"packages": {"baseline": frozen}, "input": file_record(corpus),
                            "required_free_bytes": 0, "required_tmp_free_bytes": 0, "limits": LIMITS}
                file = root / "protocol.json"
                file.write_text(json.dumps(protocol))
                args = SimpleNamespace(protocol=file, enwik9=corpus, binary=binary,
                                       role="baseline", cpu=0, output=root / "result")

                def fake_phase(command, work, limits):
                    if work.name == "encode":
                        (work / "archive9").write_bytes(archive.read_bytes())
                    else:
                        self.assertEqual(sorted(p.name for p in work.iterdir()), ["archive9"])
                        (work / "enwik9_uncompressed").write_bytes(b"bad" if wrong_restore else corpus.read_bytes())
                    return {"status": "ok"}

                with patch("release_full.Path.read_text", autospec=True, side_effect=host_text), \
                     patch("release_full.os.sched_getaffinity", create=True, return_value={0}), \
                     patch("release_full.shutil.which", return_value="/usr/bin/taskset"), \
                     patch("release_full.inspect", return_value=({"blocks": {"weights": {"sha256": "weights"}}}, b"")), \
                     patch("release_full.capture", return_value="test host"), \
                     patch("release_full.run_phase", side_effect=fake_phase):
                    rc = execute(args)
                result = json.loads((args.output / "report.json").read_text())
                self.assertEqual(result["passed"], not (wrong_restore or wrong_archive))
                self.assertEqual(rc, int(wrong_restore or wrong_archive))
                self.assertEqual(result["decoder_initial_files"], ["archive9"])
                self.assertEqual(result["packaged_bytes_with_arguments"], binary.stat().st_size + archive.stat().st_size + 19)

    @unittest.skipUnless(platform.system() == "Linux", "requires Linux /proc")
    def test_disk_counts_hardlinks_once_and_open_unlinked_files(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            file = work / "named"
            file.write_bytes(b"x" * 1234)
            os.link(file, work / "second-name")
            code = ("import os,sys,time; f=open(sys.argv[1],'w+b'); "
                    "f.truncate(2000000); os.unlink(sys.argv[1]); "
                    "print('ready',flush=True); time.sleep(10)")
            child = subprocess.Popen([sys.executable, "-c", code, str(work / "deleted")],
                                     stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                measured = sample_resources(child.pid, work)
                self.assertEqual(measured["apparent_regular_file_bytes"], 2001234)
                self.assertLess(measured["allocated_regular_file_bytes"], measured["apparent_regular_file_bytes"])
                self.assertGreater(measured["process_tree_rss_bytes"], 0)
            finally:
                child.kill()
                child.wait()
                child.stdout.close()


if __name__ == "__main__":
    unittest.main()
