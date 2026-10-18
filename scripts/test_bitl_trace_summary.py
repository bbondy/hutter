import unittest

try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, "requires optional NumPy diagnostic environment")
class BitCostTests(unittest.TestCase):
    def test_bit_value_and_discrete_probability_direction(self):
        from bitl_trace_summary import coding_cost, aggregate, cell
        base, head = coding_cost(np.array([32768, 32768, 32768], dtype=np.uint16),
                                 np.array([49152, 49152, 32768], dtype=np.uint16),
                                 np.array([2, 0, 1], dtype=np.uint8))
        np.testing.assert_array_equal(base, [1., 1., 1.])
        np.testing.assert_allclose(head, [-np.log2(0.75), 2., 1.])
        total = cell()
        aggregate(total, base, head, np.array([2, 0, 1], dtype=np.uint8), np.ones(3, dtype=bool))
        self.assertEqual((total["bits"], total["overrides"], total["helped_bits"], total["hurt_bits"]), (3, 1, 1, 1))
        self.assertAlmostEqual(total["head_bits"] - total["base_bits"], -np.log2(0.75))
        with self.assertRaisesRegex(ValueError, "probability"):
            coding_cost(np.array([0]), np.array([32768]), np.array([0]))
