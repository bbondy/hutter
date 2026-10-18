from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from competitive import ENGINE
from training_read_cache import AFTER, CPP, HEADER, apply, rewrite_cpp, rewrite_header


class ReadCacheTests(unittest.TestCase):
    def test_exact_source_guards_and_pinned_tree_protection(self):
        with self.assertRaisesRegex(ValueError, "pinned upstream"):
            apply(ENGINE)
        for path, rewrite in ((CPP, rewrite_cpp), (HEADER, rewrite_header)):
            changed = rewrite((ENGINE / path).read_text())
            with self.assertRaisesRegex(ValueError, "anchor changed"):
                rewrite(changed)

    @unittest.skipUnless(shutil.which("clang++"), "requires a C++ compiler")
    def test_compiled_reader_handles_appends_mapping_growth_and_fallback(self):
        code = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>
namespace transformer {
template<class... T> [[noreturn]] void Fail(const char*, T...) { std::exit(19); }
}
struct CoderZ3 {
  FILE* file_ = std::tmpfile();
  const unsigned char* read_map_ = nullptr;
  size_t read_map_bytes_ = 0;
  long long pos_ = 0;
  void Flush() {} // Writes below use libc's actual buffer, flushed by ReadRange.
  void ReadRange(long long,long long,unsigned char*);
  void WriteAt(long long at, const char* text) {
    assert(fseeko(file_,at,SEEK_SET)==0);
    assert(fwrite(text,1,strlen(text),file_)==strlen(text));
    if (at+(long long)strlen(text)>pos_) pos_=at+strlen(text);
  }
  ~CoderZ3() {if (read_map_) munmap((void*)read_map_,read_map_bytes_);fclose(file_);}
};
''' + AFTER + r'''
int main(int argc,char**) {
  CoderZ3 z; unsigned char out[32] = {};
  z.WriteAt(0,"first"); z.ReadRange(0,5,out); assert(memcmp(out,"first",5)==0);
  z.WriteAt(5," append"); z.ReadRange(0,12,out); assert(memcmp(out,"first append",12)==0);
  const long long boundary=64ll<<20;
  z.WriteAt(boundary-3,"across"); z.ReadRange(boundary-3,boundary+3,out);
  assert(memcmp(out,"across",6)==0 && z.read_map_bytes_==128ull<<20);
  z.ReadRange(0,12,out); assert(memcmp(out,"first append",12)==0);
  const long long cap=1ll<<30;
  z.WriteAt(cap,"fallback"); z.ReadRange(cap,cap+8,out);
  assert(memcmp(out,"fallback",8)==0 && z.read_map_bytes_==128ull<<20);
  z.ReadRange(5,12,out); assert(memcmp(out," append",7)==0);
  if (argc>1) z.ReadRange(cap+7,cap+9,out); // Must reject a future byte.
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe.cpp").write_text(code)
            subprocess.run(["clang++", "-std=c++17", "-O2", str(root / "probe.cpp"), "-o", str(root / "probe")], check=True, capture_output=True)
            subprocess.run([str(root / "probe")], check=True, capture_output=True)
            bad = subprocess.run([str(root / "probe"), "future"], capture_output=True)
            self.assertEqual(bad.returncode, 19)
