from pathlib import Path
import shutil
import tempfile
import unittest

from cmix_variants import HEADER, VARIANTS, apply_variant, model_identity, recipe, require_same_model
from competitive import ENGINE
from make_samples import digest


class ModelVariantTests(unittest.TestCase):
    def test_exact_source_edits_and_historical_baseline_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / HEADER
            path.parent.mkdir(parents=True)
            for name in VARIANTS:
                shutil.copyfile(ENGINE / HEADER, path)
                info = apply_variant(source, name)
                build = {"source_files": {HEADER: {"sha256": digest(path)}}, "model_variant": info}
                self.assertEqual(model_identity(build)[0], name)
                self.assertEqual(digest(path), info["after_sha256"])
                if name == "baseline":
                    historical = {"source_files": build["source_files"]}
                    require_same_model(build, historical)
                else:
                    with self.assertRaisesRegex(ValueError, "variants differ"):
                        require_same_model(build, historical)
                    with self.assertRaisesRegex(ValueError, "unchanged upstream"):
                        apply_variant(source, name)

    def test_modified_source_and_forged_provenance_are_rejected(self):
        _, info = recipe("z3-off")
        build = {"source_files": {HEADER: {"sha256": info["after_sha256"]}}, "model_variant": info}
        with self.assertRaisesRegex(ValueError, "source hash"):
            model_identity({"source_files": build["source_files"]})
        with self.assertRaisesRegex(ValueError, "recipe"):
            model_identity({**build, "model_variant": {**info, "z3_parameters": {"budget": 256}}})
        with self.assertRaisesRegex(ValueError, "pinned upstream"):
            apply_variant(ENGINE, "z3-off")
        with self.assertRaisesRegex(ValueError, "unknown model"):
            recipe("unrecorded")


if __name__ == "__main__":
    unittest.main()
