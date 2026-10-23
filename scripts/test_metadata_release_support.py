import shutil
import tempfile
import unittest
from pathlib import Path

from cmix_metadata_release_support import ADDED, CHANGED, VARIANT, apply
from competitive import ENGINE
from make_samples import digest


EXPECTED = {
    "src/id_exclude.h": "f1725ac236e889fee4fec6bb1454d51b21656d7cf315a30de2b3ec90fbbfc4b1",
    "src/metablock.h": "812fcaf9ea3b60887a6531bfea436c709ccf6bb699dabea2a79e7975b1881330",
    "src/metablock_form.h": "14f06282a9f7d44e945cb4699630635e498e05bd7c36ef07a6e8a8cf853db1ff",
    "src/b1_interp.h": "ece2ab298f7263502babe7a303a061e0b0222ad7bc2368f272946b6a90baae7d",
    "src/neif_levers.h": "43611740a4c5d0cf5d28435d53ad03e86820f0f4331f3b242da446ee1526a71e",
}


class MetadataReleaseTests(unittest.TestCase):
    def test_original_release_copy_gets_only_e1_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "src").mkdir()
            for name in CHANGED:
                shutil.copyfile(ENGINE / name, source / name)
            binding = apply(source, VARIANT)
            self.assertEqual(set(binding["after_sha256"]), set(CHANGED))
            self.assertEqual(set(binding["new_headers_sha256"]), set(ADDED))
            self.assertEqual({name: digest(source / name) for name in EXPECTED}, EXPECTED)
            self.assertIn("#define NEIF_E3B 0", (source / "src/neif_levers.h").read_text())
            with self.assertRaisesRegex(ValueError, "differs from pinned upstream"):
                apply(source, VARIANT)

    def test_pinned_upstream_cannot_be_modified(self):
        with self.assertRaisesRegex(ValueError, "must not modify pinned upstream"):
            apply(ENGINE, VARIANT)


if __name__ == "__main__":
    unittest.main()
