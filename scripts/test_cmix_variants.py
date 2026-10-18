from pathlib import Path
import shutil
import tempfile
import unittest

from cmix_variants import HEADER, DEPTH_HEADER, VARIANTS, apply_variant, model_identity, recipe, require_same_model
from competitive import ENGINE
from make_samples import digest


class ModelVariantTests(unittest.TestCase):
    def test_exact_source_edits_and_historical_baseline_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for name in VARIANTS:
                for header in (HEADER, DEPTH_HEADER):
                    path = source / header
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ENGINE / header, path)
                info = apply_variant(source, name)
                path = source / info["source_file"]
                build = {"source_files": {header: {"sha256": digest(source / header)}
                                          for header in (HEADER, DEPTH_HEADER)}, "model_variant": info}
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

    def test_depth_recipe_cannot_hide_a_link_context_change(self):
        _, info = recipe("depth-no-skip")
        build = {"model_variant": info, "source_files": {
            DEPTH_HEADER: {"sha256": info["after_sha256"]},
            HEADER: {"sha256": recipe("z3-off")[1]["after_sha256"]}}}
        with self.assertRaisesRegex(ValueError, "link-context source too"):
            model_identity(build)


if __name__ == "__main__":
    unittest.main()
