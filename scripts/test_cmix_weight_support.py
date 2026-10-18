from pathlib import Path
import tempfile
import unittest

from cmix_weight_support import fingerprint, stamp


class WeightBindingTests(unittest.TestCase):
    def test_fingerprint_agrees_with_standard_fnv1a_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data"
            for data, expected in ((b"", 0xcbf29ce484222325),
                                   (b"a", 0xaf63dc4c8601ec8c),
                                   (b"foobar", 0x85944171f73967e8)):
                path.write_bytes(data)
                self.assertEqual(fingerprint(path), expected)

    def test_stamp_is_confined_to_the_original_binding_function(self):
        original = "inline unsigned long long WeightsFingerprint() {\n  return 0xb263b35196aa775bULL;\n}"
        text = "// 0xb263b35196aa775b\n" + original
        updated = stamp(text, 1)
        self.assertTrue(updated.startswith("// 0xb263b35196aa775b\n"))
        self.assertIn("return 0x0000000000000001ULL;", updated)
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            stamp(updated, 2)
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            stamp(text + original, 2)


if __name__ == "__main__":
    unittest.main()
