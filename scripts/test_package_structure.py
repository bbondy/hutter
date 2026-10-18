import struct
import unittest

from package_structure import MAGIC, inspect


class PackageStructureTests(unittest.TestCase):
    def package(self):
        program = bytearray(256)
        program[:4] = b"\x7fELF"
        program[8:8 + len(MAGIC)] = MAGIC
        struct.pack_into("<6Q", program, 24, 80, 176, 512, 512, 480, 120)
        return bytes(program) + b"hintordrFX2TFWC4data" + struct.pack("<4i", 4, 4, 0, 12)

    def test_partition_and_decoder_cut_match_the_format(self):
        package = self.package()
        report, decoder = inspect(package)
        self.assertEqual(report["packed_program_bytes"], 256)
        self.assertEqual(report["decoder_prefix_bytes"], 200)
        self.assertEqual(struct.unpack_from("<6Q", decoder, 24), (80, 120, 480, 512, 480, 120))
        self.assertEqual(report["blocks"]["weights"]["bytes"], 12)
        self.assertEqual(report["component_bytes_excluding_dictionary_payload_footer_args"], len(package) + 200 + 12)

    def test_corrupt_boundaries_and_archive_footers_are_rejected(self):
        for position, fmt, value in ((32, "<Q", 177), (64, "<Q", 500),
                                     (-8, "<i", 1), (-16, "<i", 10000)):
            bad = bytearray(self.package())
            struct.pack_into(fmt, bad, position, value)
            with self.assertRaises(ValueError):
                inspect(bad)
        with self.assertRaises(ValueError):
            inspect(self.package()[:-1])


if __name__ == "__main__":
    unittest.main()
