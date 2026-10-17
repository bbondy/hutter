import unittest

from project_order import local_order


class ProjectOrderTests(unittest.TestCase):
    def test_strict_gain_within_full_corpus_distance(self):
        baseline, edges = [0, 1, 2], [set(), {0}, {1}]
        self.assertEqual(local_order(baseline, edges, [0, 0, 0], [0, 100, 200]), [1, 0, 2])
        self.assertEqual(local_order(baseline, edges, [0, 0, 0], [0, 100, 200], span=99), baseline)
        self.assertEqual(local_order([0, 1], [{1}, {0}], [0, 0], [0, 1]), [0, 1])

    def test_special_classes_stay_fixed(self):
        for kind in (1, 2, 3, 4, 5, 6, 7, 8):
            self.assertEqual(local_order([0, 1], [set(), {0}], [kind, 0], [0, 1]), [0, 1])
            self.assertEqual(local_order([0, 1], [set(), {0}], [0, kind], [0, 1]), [0, 1])

    def test_normal_regions_separated_by_special_blocks_do_not_mix(self):
        self.assertEqual(local_order([0, 1], [set(), {0}], [0, 0], [0, 10], blocks=[1, 3]), [0, 1])

    def test_multiple_passes_preserve_final_displacement_bound(self):
        baseline = list(range(6))
        edges = [set(range(i)) for i in baseline]
        ranks = [100 * i for i in baseline]
        result = local_order(baseline, edges, [0] * 6, ranks, span=100, passes=4)
        self.assertEqual(sorted(result), baseline)
        self.assertTrue(all(abs(ranks[u] - ranks[baseline[i]]) <= 100 for i,u in enumerate(result)))
        position = {u:i for i,u in enumerate(result)}
        self.assertGreater(sum(position[u] < position[v] for u,targets in enumerate(edges) for v in targets), 0)
