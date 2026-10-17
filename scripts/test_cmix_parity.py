from pathlib import Path
import tempfile
import unittest

from cmix_parity import first_difference, validate_trace


class ParityTests(unittest.TestCase):
    def test_stream_comparison_detects_prefix_and_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory)/'a', Path(directory)/'b'
            data = b'\0' * 65536 + b'abcdefgh'
            a.write_bytes(data)
            b.write_bytes(data)
            self.assertIsNone(first_difference(a, b, 8))
            b.write_bytes(data[:-1] + b'x')
            difference = first_difference(a, b, 8)
            self.assertEqual(difference['byte_offset'], 65543)
            self.assertEqual(difference['record_index'], 8192)
            self.assertEqual(difference['left_hex'], b'abcdefgh'.hex())
            b.write_bytes(data[:-1])
            self.assertEqual(first_difference(a, b)['byte_offset'], 65543)
            a.write_bytes(b'')
            b.write_bytes(b'')
            self.assertIsNone(first_difference(a, b))

    def test_empty_equal_files_do_not_prove_completed_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'initial.bin').touch()
            (root/'initial.jsonl').touch()
            (root/'initial.complete').touch()
            (root/'probabilities.bin').touch()
            (root/'trace.complete').write_text('0\n')
            self.assertTrue(validate_trace(root, init_only=True))
            self.assertTrue(validate_trace(root))

    def test_completion_counts_reject_missing_or_truncated_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'initial.bin').write_bytes(b'abcd')
            (root/'initial.jsonl').write_text('{"name":"test","bytes":4}\n')
            self.assertTrue(validate_trace(root, init_only=True))
            (root/'initial.complete').touch()
            self.assertFalse(validate_trace(root, init_only=True))
            self.assertTrue(validate_trace(root))
            (root/'trace.complete').write_text('2\n')
            (root/'probabilities.bin').write_bytes(b'\0'*8)
            self.assertTrue(validate_trace(root))
            (root/'probabilities.bin').write_bytes(b'\0'*16)
            self.assertFalse(validate_trace(root))
            (root/'trace.complete').write_text('not a count')
            self.assertTrue(validate_trace(root))

    def test_prefix_cannot_be_accepted_as_full_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'initial.bin').write_bytes(b'abcd')
            (root/'initial.jsonl').write_text('{"bytes":4}\n')
            (root/'initial.complete').touch()
            (root/'probabilities.bin').write_bytes(b'\0'*16)
            (root/'trace.complete').write_text('2\n')
            (root/'prefix.complete').write_text('2\n')
            (root/'detail.bin').write_bytes(b'abcd')
            (root/'detail.jsonl').write_text('{"event":0,"bytes":4}\n')
            self.assertFalse(validate_trace(root,event_limit=2))
            self.assertTrue(validate_trace(root))
            self.assertTrue(validate_trace(root,event_limit=3))
            (root/'detail.bin').write_bytes(b'abc')
            self.assertTrue(validate_trace(root,event_limit=2))


if __name__ == '__main__':
    unittest.main()
