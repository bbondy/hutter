import unittest

from parity_history import comparable, fixture


class ParityHistoryTests(unittest.TestCase):
    def example(self):
        phase=lambda n:{'status':'ok','input_sha256':'prepared','files':{'output':{'bytes':n}}}
        return {'scope':'cross-platform fixture',
                'phases':{'native-encode':phase(120),'linux-encode':phase(121)},
                'manifest':{'page_count':19,'source_offset':1404,
                            'samples':[{'sha256':'prepared','bytes':108927}]},
                'payload':{'equal':False},'assets':{'dictionary':{'sha256':'dict'}},
                'reference':{'image_id':'sha256:image'},
                'native_build':{'upstream_commit':'source'},
                'linux_build':{'upstream_commit':'source'}}

    def test_only_completed_fixture_encodings_are_listed(self):
        report=self.example()
        self.assertEqual(fixture(report)['linux_payload_bytes'],121)
        report['scope']='diagnostic prefix'
        self.assertIsNone(fixture(report))
        report['scope']='cross-platform fixture'
        report['phases']['linux-encode']['status']='failed'
        with self.assertRaisesRegex(ValueError,'incomplete'):
            fixture(report)

    def test_comparison_requires_identical_input_and_assets(self):
        first=fixture(self.example())
        second=fixture(self.example())
        comparable(first,second)
        second['linux_payload_bytes']=117
        comparable(first,second)
        second['assets']={'dictionary':{'sha256':'changed'}}
        with self.assertRaisesRegex(ValueError,'assets'):
            comparable(first,second)
        second['assets']=first['assets']
        second['input_sha256']='other'
        with self.assertRaisesRegex(ValueError,'input_sha256'):
            comparable(first,second)


if __name__=='__main__':unittest.main()
