"""Bounded mapped history reads for diagnostic builds only, with exact anchors."""
from pathlib import Path

from competitive import ENGINE
from make_samples import digest

CPP = "src/tf1/tf1_z3.cpp"
HEADER = "src/tf1/tf1_z3.h"
BEFORE = '''void CoderZ3::ReadRange(long long a, long long b, unsigned char* dst) {
  if (b <= a) return;
  Flush();
  if (fseeko(file_, (off_t)a, SEEK_SET) != 0) {
    transformer::Fail("link context: seek to %lld failed", a);
  }
  const size_t n = (size_t)(b - a);
  if (fread(dst, 1, n, file_) != n) {
    transformer::Fail("link context: short read [%lld,%lld)", a, b);
  }
}'''
AFTER = '''void CoderZ3::ReadRange(long long a, long long b, unsigned char* dst) {
  if (b <= a) return;
  if (a < 0 || b > pos_) {
    transformer::Fail("link context: read beyond observed history [%lld,%lld)", a, b);
  }
  Flush();
  // Flush both the explicit append buffer and libc's buffer before mapping.
  if (fflush(file_) != 0) transformer::Fail("link context: flush failed");
  const size_t n = (size_t)(b - a);
  const size_t cap = size_t(1) << 30;
  if ((unsigned long long)b > cap) {
    // Keep memory bounded if this diagnostic is reused on a larger stream.
    if (fseeko(file_, (off_t)a, SEEK_SET) != 0 || fread(dst, 1, n, file_) != n)
      transformer::Fail("link context: fallback read failed [%lld,%lld)", a, b);
    return;
  }
  if ((size_t)b > read_map_bytes_) {
    const size_t chunk = size_t(64) << 20;
    const size_t bytes = ((size_t)b + chunk - 1) / chunk * chunk;
    // The mapping can extend past EOF, but only flushed, observed bytes are
    // accessed. Appends become visible through the shared file mapping.
    void* next = mmap(nullptr, bytes, PROT_READ, MAP_SHARED, fileno(file_), 0);
    if (next == MAP_FAILED) transformer::Fail("link context: read mapping failed");
    if (read_map_ && munmap((void*)read_map_, read_map_bytes_) != 0)
      transformer::Fail("link context: read unmapping failed");
    read_map_ = (const unsigned char*)next;
    read_map_bytes_ = bytes;
  }
  memcpy(dst, read_map_ + (size_t)a, n);
}'''


def rewrite_cpp(text):
    close = "  if (file_) fclose(file_);"
    if text.count(BEFORE) != 1 or text.count(close) != 1:
        raise ValueError("read-cache source anchor changed")
    return text.replace(BEFORE, AFTER).replace(close,
        "  if (read_map_) munmap((void*)read_map_, read_map_bytes_);\n" + close)


def rewrite_header(text):
    anchor = "  FILE* file_ = nullptr;              // the token stream on disk"
    if text.count(anchor) != 1 or "read_map_bytes_" in text:
        raise ValueError("read-cache header anchor changed")
    return text.replace(anchor, anchor + "\n  const unsigned char* read_map_ = nullptr;\n  size_t read_map_bytes_ = 0;")


def apply(source):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("read cache must not modify pinned upstream")
    files = {}
    for name, rewrite in ((CPP, rewrite_cpp), (HEADER, rewrite_header)):
        path = source / name
        before = digest(path)
        path.write_text(rewrite(path.read_text()))
        files[name] = {"before_sha256": before, "after_sha256": digest(path)}
    return {"recipe_sha256": digest(Path(__file__)), "files": files,
            "mapping_chunk_bytes": 64 << 20, "mapping_cap_bytes": 1 << 30,
            "scope": "Diagnostic-only history reader. Shared file mapping, flush before read, observed-position guard, bounded growth and stdio fallback; dump identity remains a separate acceptance gate."}
