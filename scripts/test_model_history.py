import copy
import unittest
import tempfile
from pathlib import Path
import shutil
import hashlib
from unittest.mock import patch

from cmix_variants import HEADER, DEPTH_HEADER, recipe
from competitive import ENGINE
from make_samples import digest
from model_history import compatible_builds
import cmix_retrieval_support as retrieval
import cmix_alias_support as alias
import cmix_activity_support as activity
import cmix_bit_trace_support as bit_trace
import cmix_bit_weight_support as bit_weight


class ModelComparisonTests(unittest.TestCase):
    def build(self, name):
        _, info = recipe(name)
        sources = {header: {"sha256": digest(ENGINE / header)} for header in (HEADER, DEPTH_HEADER)}
        sources[info["source_file"]] = {"sha256": info["after_sha256"]}
        return {**{key: "same" for key in ("upstream_commit", "simde_commit", "compiler", "port_files",
                                          "parity_files", "fixture_support", "initialization", "platform", "machine")},
                "command": ["make", "-j4", "CC=clang++ -Isrc -I../simde", "cmix"],
                "model_variant": info,
                "source_files": {**sources, "model.cpp": {"sha256": "unchanged"}}}

    def test_only_declared_model_change_and_build_parallelism_are_allowed(self):
        baseline, candidate = self.build("baseline"), self.build("z3-budget128")
        baseline["command"][1] = "-j8"
        self.assertEqual(compatible_builds(baseline, candidate), "z3-budget128")
        for key in ("compiler", "fixture_support", "simde_commit"):
            bad = {**candidate, key: "changed"}
            with self.assertRaisesRegex(ValueError, "uncontrolled build"):
                compatible_builds(baseline, bad)
        bad = copy.deepcopy(candidate)
        bad["source_files"]["model.cpp"]["sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "beyond declared"):
            compatible_builds(baseline, bad)
        bad = {**candidate, "command": [*candidate["command"], "EXTRA=-ffast-math"]}
        with self.assertRaisesRegex(ValueError, "compiler command"):
            compatible_builds(baseline, bad)

    def test_depth_change_requires_an_unchanged_reference_header(self):
        baseline, candidate = self.build("baseline"), self.build("depth-tau9")
        self.assertEqual(compatible_builds(baseline, candidate), "depth-tau9")
        baseline["source_files"][DEPTH_HEADER]["sha256"] = "unrecorded threshold"
        with self.assertRaisesRegex(ValueError, "undeclared adaptive-depth"):
            compatible_builds(baseline, candidate)
        with self.assertRaisesRegex(ValueError, "unchanged baseline model"):
            compatible_builds(candidate, self.build("depth-no-skip"))

    def test_retrieval_requires_exact_source_transformation(self):
        self.check_source_transformation(retrieval, "retrieval_variant", "retrieval-exact-target")

    def test_alias_refresh_requires_exact_source_transformation(self):
        self.check_source_transformation(alias, "alias_variant", "alias-refresh")

    def test_activity_requires_exact_source_transformation(self):
        self.check_source_transformation(activity, "activity_variant", "activity-mlp")

    def test_bit_trace_requires_exact_source_transformation(self):
        self.check_source_transformation(bit_trace, "bit_trace_variant", "bit-trace-fixture")

    def test_historical_reader_correction_still_requires_identical_generated_cpp(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / bit_trace.SOURCE
            path.parent.mkdir(parents=True)
            shutil.copy2(ENGINE / bit_trace.SOURCE, path)
            baseline, candidate = self.build("baseline"), self.build("baseline")
            baseline["source_files"][bit_trace.SOURCE] = {"sha256": digest(path)}
            info = bit_trace.apply(source, bit_trace.VARIANT)
            candidate["commit"] = "9ad3a7d3000d1b0f113049cd622c23e94b7eb300"
            historical = b"historical recipe with unchanged generated C++ and an older reader"
            info["recipe_sha256"] = hashlib.sha256(historical).hexdigest()
            candidate["bit_trace_variant"] = info
            candidate["source_files"][bit_trace.SOURCE] = {"sha256": info["after_sha256"]}
            shutil.copy2(ENGINE / bit_trace.SOURCE, path)
            with patch("model_history.subprocess.check_output", return_value=historical):
                self.assertEqual(compatible_builds(baseline, candidate, source), "bit-trace-fixture")
                info["recipe_sha256"] = "forged historical recipe"
                with self.assertRaisesRegex(ValueError, "historical source recipe differs"):
                    compatible_builds(baseline, candidate, source)

    def test_bit_weights_require_exact_frozen_array_transformation(self):
        self.check_source_transformation(bit_weight, "bit_weight_variant", "bit-weight-" + bit_weight.VARIANT)

    def check_source_transformation(self, module, field, model_name):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original"
            candidate_dir = Path(directory) / "candidate"
            for folder in (original, candidate_dir):
                path = folder / module.SOURCE
                path.parent.mkdir(parents=True)
                shutil.copyfile(ENGINE / module.SOURCE, path)
            baseline, candidate = self.build("baseline"), self.build("baseline")
            baseline["source_files"][module.SOURCE] = {"sha256": digest(original / module.SOURCE)}
            info = module.apply(candidate_dir, module.VARIANT)
            candidate[field] = info
            candidate["source_files"][module.SOURCE] = {"sha256": info["after_sha256"]}
            self.assertEqual(compatible_builds(baseline, candidate, original), model_name)
            with self.assertRaisesRegex(ValueError, "baseline source file"):
                compatible_builds(baseline, candidate)
            bad = copy.deepcopy(candidate)
            forged = hashlib.sha256((candidate_dir / module.SOURCE).read_bytes() + b"\nint undeclared;\n").hexdigest()
            bad[field]["after_sha256"] = forged
            bad["source_files"][module.SOURCE]["sha256"] = forged
            with self.assertRaisesRegex(ValueError, "more than the declared"):
                compatible_builds(baseline, bad, original)
            with self.assertRaisesRegex(ValueError, "anchor changed"):
                module.apply(candidate_dir, module.VARIANT)
            with self.assertRaisesRegex(ValueError, "pinned upstream"):
                module.apply(ENGINE, module.VARIANT)


if __name__ == "__main__":
    unittest.main()
