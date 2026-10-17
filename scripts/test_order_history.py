import copy
import unittest

from article_order import sha
from order_history import checked_restoration, same_setup
from test_article_order import page


class OrderHistoryTests(unittest.TestCase):
    def test_allows_reordered_input_but_rejects_different_model_or_assets(self):
        metadata = dict(binary_sha256='binary', side_data={'weights': 'hash'}, build={'source': 'hash'},
                        native_arguments=['--native-pages', '2'], runner_sha256='runner',
                        platform='mac', machine='arm64', input_sha256='original')
        reordered = {**metadata, 'input_sha256': 'reordered'}
        same_setup([metadata, reordered])
        for key in ('binary_sha256', 'side_data', 'build', 'native_arguments', 'runner_sha256'):
            bad = copy.deepcopy(reordered)
            bad[key] = 'changed'
            with self.assertRaises(ValueError):
                same_setup([metadata, bad])
        with self.assertRaises(ValueError):
            same_setup([{}, {}])

    def test_requires_same_article_set_and_exact_original_restoration(self):
        a, b = page(1, 'A', '[[B]]'), page(2, 'B', 'text')
        sample = {'ordered_raw_sha256': sha(b+a), 'page_ids': [2, 1]}
        manifest = {'page_count': 2, 'page_set_sha256': sha('\n'.join(sorted([sha(a), sha(b)])).encode()),
                    'raw_bytes': len(a+b), 'raw_sha256': sha(a+b)}
        self.assertEqual(checked_restoration(b+a, sample, manifest), sha(a+b))
        for key, value in [('page_count', 3), ('page_set_sha256', 'other'),
                           ('raw_sha256', sha(b+a)), ('raw_bytes', 1)]:
            with self.assertRaises(ValueError):
                checked_restoration(b+a, sample, {**manifest, key: value})
        with self.assertRaises(ValueError):
            checked_restoration(a+b, sample, manifest)


if __name__ == '__main__':
    unittest.main()
