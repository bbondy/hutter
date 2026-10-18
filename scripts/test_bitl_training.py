from pathlib import Path
import struct
import tempfile
import unittest

from bitl_training import weight_info


class TrainedWeightTests(unittest.TestCase):
    def test_shape_finiteness_padding_and_truncation_for_both_precisions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights"
            for version in (1, 2):
                width = 4 if version == 1 else 2
                header = b"NBLB" + struct.pack("<I4i", version, 16, 89, 96, 28)
                original = header + bytes(3681*width)
                path.write_bytes(original)
                self.assertEqual(weight_info(path, version)["bytes"], len(original))
                for bits, index in ((0x7fc00000, 3), (0x3f800000, 90)):
                    data = bytearray(original)
                    replacement = struct.pack("<I", bits) if version == 1 else struct.pack("<H", bits >> 16)
                    data[24+index*width:24+(index+1)*width] = replacement
                    path.write_bytes(data)
                    with self.assertRaisesRegex(ValueError, "nonfinite weight or nonzero input padding"):
                        weight_info(path, version)
                path.write_bytes(original[:-1])
                with self.assertRaisesRegex(ValueError, "length"):
                    weight_info(path, version)
            path.write_bytes(b"NBLB")
            with self.assertRaisesRegex(ValueError, "geometry"):
                weight_info(path, 2)
