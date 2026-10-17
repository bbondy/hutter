import copy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from cmix_fixture_support import (CAPABILITY, HEADER, context_report, corpus_arguments,
                                  instrument_fixture, validate_context)
from competitive import ENGINE


class FixtureSupportTests(unittest.TestCase):
    def test_manifest_configuration_and_build_compatibility(self):
        good = {"page_count": 10, "redirect_prefix_count": 2, "helper_arguments": ["--native-corpus", "10", "2"]}
        build = {"fixture_support": {"capability": CAPABILITY}}
        self.assertEqual(corpus_arguments(good, build), ["--native-corpus", "10", "2"])
        self.assertEqual(corpus_arguments({"page_count": 10}, {}), ["--native-pages", "10"])
        for bad in ({**good, "page_count": True}, {**good, "page_count": 0},
                    {**good, "redirect_prefix_count": 11}, {**good, "redirect_prefix_count": -1}):
            with self.assertRaises(ValueError):
                corpus_arguments(bad, build)
        with self.assertRaises(ValueError):
            corpus_arguments(good, {})
        with self.assertRaisesRegex(ValueError, "fixture helper"):
            corpus_arguments({"page_count": 10, "redirect_prefix_count": 2}, build)

    def test_context_requires_equal_counts_and_correct_phase(self):
        report = {"z3": {"fed_tokens": 20}, "prompt": {"articles": 10, "redirect_prompt_pages": 1},
                  "alias": {"bytes": 5}}
        manifest = {"page_count": 10, "redirect_prefix_count": 2}
        validate_context(report, copy.deepcopy(report), manifest)
        for bad in ({**report, "z3": {"fed_tokens": 19}}, {"prompt": report["prompt"]}):
            with self.assertRaises(ValueError):
                validate_context(report, bad, manifest)
        with self.assertRaises(ValueError):
            validate_context(report, report, {**manifest, "redirect_prefix_count": 3})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log'
            path.write_text('progress\rCMIX_CONTEXT ' + json.dumps({"kind": "z3", "fed_tokens": 20}) + '\n')
            self.assertEqual(context_report(path), {"z3": {"fed_tokens": 20}})
            path.write_text(path.read_text() * 2)
            with self.assertRaises(ValueError):
                context_report(path)

    def test_shared_patch_consumes_every_cutoff_and_fails_on_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            for name in ('redirect_table.h', 'runner.cpp', 'alias_context.h',
                         'tf1/tf1_prompt.h', 'tf1/tf1_prompt.cpp', 'tf1/tf1_z3.cpp', 'tf1/tf1_engine.cpp'):
                dest = source / 'src' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ENGINE / 'src' / name, dest)
            instrument_fixture(source)
            for name in ('redirect_table.h', 'tf1/tf1_prompt.h'):
                self.assertNotIn('71148', (source / 'src' / name).read_text())
            with self.assertRaises(ValueError):
                instrument_fixture(source)


@unittest.skipUnless(shutil.which('clang++'), 'requires C++17 compiler')
class CorpusHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        source = cls.root / 'check.cpp'
        source.write_text('''#include "native_corpus.h"
#include <fstream>
int main(int argc, char** argv) {
  if (!native_corpus::Configure(&argc, argv)) return 2;
  if (argc == 1) return native_corpus::PageCount() == 243425 && native_corpus::RedirectCount() == 71148 ? 0 : 3;
  if (std::strcmp(argv[1], "-d") == 0) {
    std::ifstream in(argv[3], std::ios::binary);
    if (!native_corpus::ReadHeader(&in) || in.get() != 'x') return 4;
  } else {
    std::ofstream out(argv[4], std::ios::binary);
    if (!native_corpus::WriteHeader(&out)) return 5;
    out.put('x');
  }
}
''')
        cls.binary = cls.root / 'check'
        subprocess.run(['clang++', '-std=c++17', '-I' + str(HEADER.parent), str(source), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def invoke(self, *args):
        return subprocess.run([str(self.binary), *map(str, args)], capture_output=True).returncode

    def test_release_defaults_legacy_and_explicit_header_roundtrip(self):
        archive = self.root / 'payload'
        self.assertEqual(self.invoke(), 0)
        for flags, expected in (([], b'x'), (['--native-pages', '7'], b'x'),
                                (['--native-corpus', '7', '0'], b'HUTDEV2\0' + struct.pack('<II', 7, 0) + b'x'),
                                (['--native-corpus', '7', '7'], b'HUTDEV2\0' + struct.pack('<II', 7, 7) + b'x')):
            self.assertEqual(self.invoke(*flags, '-c', 'dict', 'in', archive), 0)
            self.assertEqual(archive.read_bytes(), expected)
            self.assertEqual(self.invoke(*flags, '-d', 'dict', archive, 'out'), 0)

    def test_mismatches_corruption_and_invalid_parameters_fail_early(self):
        archive = self.root / 'mismatch'
        self.assertEqual(self.invoke('--native-corpus', 7, 2, '-c', 'dict', 'in', archive), 0)
        for flags in ([], ['--native-pages', '7'], ['--native-corpus', '8', '2'], ['--native-corpus', '7', '3']):
            self.assertEqual(self.invoke(*flags, '-d', 'dict', archive, 'out'), 2)
        for data in (b'x', b'HUTDEV2\0', b'HUTDEV3\0' + struct.pack('<II', 7, 2)):
            archive.write_bytes(data)
            self.assertEqual(self.invoke('--native-corpus', 7, 2, '-d', 'dict', archive, 'out'), 2)
        for n, r in (('0', '0'), ('243426', '0'), ('7', '8'), ('-1', '0'), (' 7', '0'), ('7', '-1')):
            self.assertEqual(self.invoke('--native-corpus', n, r, '-c', 'dict', 'in', archive), 2)
        self.assertEqual(self.invoke('--native-corpus', 7), 2)


@unittest.skipUnless(shutil.which('clang++'), 'requires C++17 compiler')
class PreparationPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        source = cls.root / 'source'
        shutil.copytree(ENGINE, source)
        shutil.copyfile(HEADER, source / 'src/native_corpus.h')
        instrument_fixture(source)
        cls.binary = cls.root / 'prepare-sample'
        subprocess.run(['clang++', '-O1', '-std=c++17', '-I' + str(source / 'src'),
                        str(HEADER.parents[2] / 'prepare_sample.cpp'), '-o', str(cls.binary)],
                       check=True, capture_output=True)
        def page(pid, title, text):
            return (f'  <page>\n    <title>{title}</title>\n    <id>{pid}</id>\n'
                    f'    <revision>\n      <id>{100+pid}</id>\n'
                    '      <timestamp>2005-01-01T00:00:00Z</timestamp>\n'
                    '      <contributor>\n        <username>Tester</username>\n'
                    '        <id>42</id>\n      </contributor>\n'
                    f'      <text xml:space="preserve">{text}</text>\n'
                    '    </revision>\n  </page>\n').encode()
        cls.raw = cls.root / 'raw.xml'
        cls.raw.write_bytes(page(1, 'Redirect', '#REDIRECT [[Target]]')
                            + page(2, 'Target', 'Ordinary body [[Third]].')
                            + page(3, 'Third', 'Another ordinary body.'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def invoke(self, *args):
        return subprocess.run([str(self.binary), *map(str, args)], capture_output=True)

    def test_phase_configuration_reaches_text_transform_and_inverse(self):
        outputs = {}
        for redirects in (0, 1, 3):
            flags = ['--native-corpus', 3, redirects]
            ready, restored = self.root / f'{redirects}.ready', self.root / f'{redirects}.xml'
            self.assertEqual(self.invoke(*flags, 'encode', self.raw, ready).returncode, 0)
            self.assertEqual(self.invoke(*flags, 'decode', ready, restored).returncode, 0)
            self.assertEqual(restored.read_bytes(), self.raw.read_bytes())
            outputs[redirects] = ready.read_bytes()
        self.assertIn(b'#REDIRECT', outputs[0])
        self.assertNotIn(b'#REDIRECT', outputs[1])
        self.assertNotIn(b'\x01Ordinary body', outputs[1])
        self.assertIn(b'\x01Ordinary body', outputs[3])
        legacy = self.root / 'legacy.ready'
        self.assertEqual(self.invoke('encode', self.raw, legacy).returncode, 0)
        self.assertEqual(legacy.read_bytes(), outputs[3])

    def test_helper_rejects_incorrect_declared_page_count(self):
        result = self.invoke('--native-corpus', 4, 1, 'encode', self.raw, self.root / 'wrong.ready')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'3 observed, 4 declared', result.stderr)
