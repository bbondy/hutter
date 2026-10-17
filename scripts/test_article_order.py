import unittest

from article_order import graph_order, link_graph, orders_for, pages_from_bytes, restore_source


def page(page_id, title, text):
    return (f'  <page>\n    <title>{title}</title>\n    <id>{page_id}</id>\n'
            f'    <revision><id>999</id><text xml:space="preserve">{text}</text></revision>\n'
            '  </page>\n').encode()


class ArticleOrderTests(unittest.TestCase):
    def test_graph_direction_and_exact_link_semantics(self):
        pages = pages_from_bytes(page(1, 'A &amp; B', '[[C#part|alias]] [[C]] [[c]] [[A &amp; B]]')
                                 + page(2, 'C', '[[A &amp; B]] [[A_&amp;_B]]'))
        self.assertEqual(link_graph(pages), [{1}, {0}])

    def test_cycle_and_disconnected_graph_preserve_all_pages(self):
        edges = [{1}, {2}, {0, 3}, set(), set(), {4}]
        order, sizes = graph_order(edges)
        self.assertEqual(sorted(order), list(range(6)))
        self.assertEqual(sizes, [3, 1, 1, 1])
        self.assertLess(order.index(2), order.index(3))
        self.assertLess(order.index(5), order.index(4))
        self.assertEqual(graph_order(edges), (order, sizes))

    def test_dag_prioritizes_sources_even_when_ids_run_backwards(self):
        order, _ = graph_order([set(), {0}, {1}])
        self.assertEqual(order, [2, 1, 0])
        self.assertEqual(graph_order([set(), set(), set()])[0], [0, 1, 2])

    def test_each_order_restores_exact_original_without_permutation(self):
        raw = page(10, 'A', 'same\nbytes') + page(20, 'B', '[[A]]') + page(30, 'C', '[[B]]')
        pages = pages_from_bytes(raw)
        orders, metrics = orders_for(pages, 123)
        self.assertEqual(metrics['variants']['graph']['forward_edges'], 2)
        self.assertEqual(metrics['variants']['source']['forward_edges'], 0)
        self.assertEqual(orders_for(pages, 123)[0], orders)
        for order in orders.values():
            self.assertEqual(restore_source(b''.join(pages[i]['raw'] for i in order)), raw)

    def test_reject_lossy_or_ambiguous_inputs(self):
        raw = page(1, 'A', 'x')
        for bad in (b'header' + raw, raw[:-2], raw + raw,
                    raw + page(2, 'A', 'y'), raw + page(1, 'B', 'y')):
            with self.assertRaises(ValueError):
                pages_from_bytes(bad)


if __name__ == '__main__':
    unittest.main()
