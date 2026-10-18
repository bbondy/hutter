import copy
import unittest

from cmix_variants import HEADER, DEPTH_HEADER, recipe
from competitive import ENGINE
from make_samples import digest
from model_history import compatible_builds


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


if __name__ == "__main__":
    unittest.main()
