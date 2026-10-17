from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from competitive import differences, inventory, problems


class CompetitiveTests(unittest.TestCase):
    def test_inventory_detects_content_mode_missing_and_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.cpp").write_text("original")
            (root / "build.sh").write_text("script")
            (root / "weights").write_bytes(b"weights")
            expected = inventory(root)
            self.assertFalse(any(differences(expected, inventory(root)).values()))
            (root / "model.cpp").write_text("modified")
            (root / "build.sh").chmod(0o755)
            (root / "weights").unlink()
            (root / "extra").write_text("new")
            self.assertEqual(differences(expected, inventory(root)), {
                "changed": ["build.sh", "model.cpp"], "missing": ["weights"], "added": ["extra"]})

    @patch("competitive.platform.system", return_value="Darwin")
    @patch("competitive.platform.machine", return_value="arm64")
    @patch("competitive.subprocess.run")
    def test_unsupported_host_does_not_execute_tools(self, run, machine, system):
        self.assertIn("Requires Linux x86-64", problems()[0])
        run.assert_not_called()

    @patch("competitive.platform.system", return_value="Linux")
    @patch("competitive.platform.machine", return_value="aarch64")
    def test_linux_arm_is_not_treated_as_compatible(self, machine, system):
        self.assertTrue(problems())


if __name__ == "__main__":
    unittest.main()
