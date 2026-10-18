import unittest

try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, "requires the NumPy research environment")
class DumpVocabularyTests(unittest.TestCase):
    def test_sentinels_are_input_only_and_previous_reset_marker_is_allowed(self):
        from training_dump_summary import ROW, validate_token_roles
        rows = np.zeros(3, dtype=ROW)
        rows["src"] = [0, -1, -1]
        rows["flags"] = [4, 3, 3]
        rows["tok"] = [0, 208, 215]
        rows["prev1"][0] = rows["prev2"][0] = 216
        counts = validate_token_roles(rows)
        self.assertEqual(counts.tolist(), [1, 0, 0, 0, 0, 0, 0, 1])
        for field, value in (("src", 1), ("tok", 216), ("flags", 2)):
            bad = rows.copy()
            bad[field][1] = value
            with self.assertRaisesRegex(ValueError, "token role"):
                validate_token_roles(bad)
