from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cmix_preprocess_support import HEADER, apply_portable_preprocessing
from competitive import ENGINE


@unittest.skipUnless(shutil.which('clang++'), 'requires C++ compiler')
class EntityPortabilityTests(unittest.TestCase):
    def test_entity_reduction_with_optimization_and_overflow_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            shutil.copytree(ENGINE, source)
            info = apply_portable_preprocessing(source)
            self.assertNotEqual(info['before_sha256'], info['after_sha256'])
            with self.assertRaisesRegex(ValueError, 'exactly two'):
                apply_portable_preprocessing(source)
            driver = root / 'entities.cpp'
            driver.write_text('''#include <cstdint>
#include <cstring>
#include <unistd.h>
#include <string>
#include <vector>
#include <algorithm>
#include "readalike_prepr/phda9_preprocess.h"
int main() {
  char in[128] = "&lt; &gt;", out[128] = {};
  hent(in, out);
  if (strcmp(out, "&< &>")) return 1;
  strcpy(in, "&&lt; &&gt;");
  hent2(in, out);
  if (strcmp(out, "&&< &&>")) return 2;
  return 0;
}
''')
            for opt in ('-O2', '-Oz'):
                binary = root / ('check' + opt)
                subprocess.run(['clang++', opt, '-std=c++17', '-Wno-deprecated-declarations',
                                '-fsanitize=signed-integer-overflow', '-fno-sanitize-recover=all',
                                '-I' + str(source / 'src'), str(driver), '-o', str(binary)],
                               check=True, capture_output=True)
                subprocess.run([str(binary)], check=True, capture_output=True)
            # The original arithmetic is not merely a different coding choice:
            # the same semantic test triggers signed-overflow instrumentation.
            shutil.copyfile(ENGINE / HEADER, source / HEADER)
            binary = root / 'original'
            subprocess.run(['clang++', '-O2', '-std=c++17', '-Wno-deprecated-declarations',
                            '-fsanitize=signed-integer-overflow', '-fno-sanitize-recover=all',
                            '-I' + str(source / 'src'), str(driver), '-o', str(binary)],
                           check=True, capture_output=True)
            result = subprocess.run([str(binary)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'signed integer overflow', result.stderr)


if __name__ == '__main__':
    unittest.main()
