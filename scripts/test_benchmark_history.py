import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from benchmark_history import aggregates, compare, record


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.row = {"input": "/old/path/sample", "input_bytes": 100,
                    "input_sha256": "corpus-a", "codec": "ppmd", "roundtrip": True,
                    "repeat_matches": True, "archive_bytes": 40, "archive_sha256": "archive-a",
                    "compress": {"wall_seconds": 2, "peak_rss_bytes": 1000},
                    "decompress": {"wall_seconds": 3, "peak_rss_bytes": 2000}}

    def run_dir(self, name, rows):
        path = self.root / name
        path.mkdir()
        (path / "metadata.json").write_text(json.dumps({"commit": "abc", "cpu": "test"}))
        (path / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        return path

    def test_record_is_immutable_and_survives_source_removal(self):
        source = self.run_dir("run", [self.row])
        with contextlib.redirect_stdout(io.StringIO()):
            saved = record(source, "baseline", "test", root=self.root / "history")
        with self.assertRaises(FileExistsError):
            record(source, "baseline", "replace", root=self.root / "history")
        (source / "results.jsonl").unlink()
        self.assertEqual(len(aggregates(saved)), 1)

    def test_comparison_uses_content_and_reports_regression(self):
        before = self.run_dir("before", [self.row])
        changed = copy.deepcopy(self.row)
        changed.update(input="/new/path/renamed", archive_bytes=45, archive_sha256="archive-b")
        after = self.run_dir("after", [changed])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            compare(before, after)
        self.assertIn("| +5 | +12.500% |", output.getvalue())
        changed["input_sha256"] = "different-input"
        other = self.run_dir("other", [changed])
        with self.assertRaisesRegex(ValueError, "no matching"):
            compare(before, other)

    def test_failed_or_nondeterministic_trials_cannot_win(self):
        failed = {**self.row, "roundtrip": False}
        self.assertFalse(aggregates(self.run_dir("failed", [self.row, failed])))
        different = {**self.row, "archive_sha256": "different-archive"}
        self.assertFalse(aggregates(self.run_dir("unstable", [self.row, different])))

    def test_phase_mismatch_and_invalid_context_cannot_win(self):
        before = self.run_dir("legacy", [self.row])
        after = self.run_dir("corrected", [self.row])
        (before / "metadata.json").write_text(json.dumps({"native_arguments": ["--native-pages", "19"]}))
        (after / "metadata.json").write_text(json.dumps({"native_arguments": ["--native-corpus", "19", "4"]}))
        with self.assertRaisesRegex(ValueError, "phase arguments"):
            compare(before, after)
        self.assertFalse(aggregates(self.run_dir("context-failure", [{**self.row, "context_valid": False}])))

    def test_invalid_manifest_and_id_leave_no_history(self):
        source = self.run_dir("run", [self.row])
        manifest = self.root / "manifest.json"
        manifest.write_text('{"samples": []}')
        history = self.root / "history"
        with self.assertRaises(ValueError):
            record(source, "baseline", "test", manifest, history)
        with self.assertRaises(ValueError):
            record(source, "../escape", "test", root=history)
        self.assertFalse(history.exists())


if __name__ == "__main__":
    unittest.main()
