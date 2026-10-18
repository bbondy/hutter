import unittest

from weight_equivalence import tradeoff


class WeightTradeoffTests(unittest.TestCase):
    def test_two_weight_copies_and_full_corpus_scaling_are_counted(self):
        base = {"weight_bytes": 1000000, "payload_bytes": 100000}
        candidate = {"weight_bytes": 900000, "payload_bytes": 100100}
        row = tradeoff(base, candidate, 1000000)
        self.assertEqual(row["gross_two_container_delta_bytes"], -200000)
        self.assertEqual(row["projected_full_payload_delta_bytes"], 100000)
        self.assertEqual(row["projected_payload_plus_containers_delta_bytes"], -100000)
        self.assertTrue(row["within_gross_budget"])
        self.assertFalse(tradeoff(base, {**candidate, "payload_bytes": 100201}, 1000000)["within_gross_budget"])

    def test_break_even_is_not_a_win_and_different_sample_lengths_matter(self):
        base = {"weight_bytes": 1000, "payload_bytes": 100}
        candidate = {"weight_bytes": 500, "payload_bytes": 101}
        self.assertFalse(tradeoff(base, candidate, 1000000)["within_gross_budget"])
        self.assertTrue(tradeoff(base, candidate, 2000000)["within_gross_budget"])
        self.assertFalse(tradeoff(base, candidate, 500000)["within_gross_budget"])
        with self.assertRaises(ValueError):
            tradeoff(base, candidate, 0)


if __name__ == "__main__":
    unittest.main()
