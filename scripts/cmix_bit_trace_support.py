"""Bounded, read-only BITLSTM traces on disposable development builds."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from competitive import ENGINE
from make_samples import digest

SOURCE = "src/bit_head.cpp"
VARIANT = "fixture"
MAX_BITS = 16_000_000
TRACE_HEADER = struct.pack("<5IQ", 0x4c544942, 3, 28, 60, 0, 0x07e0007f)
CHANNEL_HEADER = struct.pack("<7I", 0x315a4142, 4, 32, 1, 32, 1, 1)
WRITER_CPP = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
namespace hutter_bit_trace {
struct Writer {
  FILE* trace = nullptr;
  FILE* channel = nullptr;
  FILE* probability = nullptr;
  char names[3][96] = {};
  unsigned long long count = 0, channels = 0;
  bool pending = false;
  unsigned char row[60] = {};
  static void Require(bool condition) {
    if (!condition) {
      std::fputs("BITL trace: invalid state or I/O failure\n", stderr);
      std::exit(91);
    }
  }
  static void Write(FILE* f, const void* p, size_t n) {
    Require(std::fwrite(p, 1, n, f) == n);
  }
  void Open() {
    static_assert(sizeof(float) == 4, "trace needs binary32");
    const uint32_t endian = 1;
    Require(*(const unsigned char*)&endian == 1);
    const char* roles[] = {"trace", "channel", "probability"};
    FILE** files[] = {&trace, &channel, &probability};
    for (int j = 0; j < 3; ++j) {
      std::snprintf(names[j], sizeof(names[j]), "bitl-%s-%ld.bin", roles[j], (long)getpid());
      const int fd = open(names[j], O_WRONLY | O_CREAT | O_EXCL, 0600);
      Require(fd >= 0);
      *files[j] = fdopen(fd, "wb");
      Require(*files[j] != nullptr);
    }
    const uint32_t th[] = {0x4c544942, 3, 28, 60, 0};
    const uint64_t mask = 0x07e0007f;
    const uint32_t ch[] = {0x315a4142, 4, 32, 1, 32, 1, 1};
    Write(trace, th, sizeof(th)); Write(trace, &mask, sizeof(mask));
    Write(channel, ch, sizeof(ch));
  }
  void Prepare(unsigned long long index, unsigned int base_p, const float* stage1,
               int n_stage1, float m1raw, int override_active,
               const float* tf, int n_tf, const float* hid, const float* lhid,
               const unsigned int* zone) {
    Require(!pending && index == count && count < 16000000ULL &&
            base_p >= 1 && base_p <= 65535 && n_stage1 == 28 &&
            (override_active == 0 || override_active == 1));
    if (!trace) Open();
    const uint16_t bp = (uint16_t)base_p;
    std::memcpy(row, &bp, 2);
    row[2] = (unsigned char)override_active; row[3] = 0;
    std::memcpy(row + 4, &m1raw, 4);
    int offset = 8;
    for (int j = 0; j < 28; ++j) {
      if (j > 6 && (j < 21 || j > 26)) continue;
      std::memcpy(row + offset, stage1 + j, 4); offset += 4;
    }
    Require(offset == 60);
    if ((count & 7) == 0) {
      float values[69] = {};
      for (int j = 0; j < 4; ++j) values[j] = (tf && j < n_tf) ? tf[j] : 0.0f;
      // Copy the projections already calculated by the live head. Do not
      // recompute them with a different reduction order or byte alignment.
      std::memcpy(values + 4, hid, 32 * sizeof(float));
      std::memcpy(values + 36, lhid, 32 * sizeof(float));
      values[68] = zone ? (float)*zone : 0.0f;
      Write(channel, values, sizeof(values)); ++channels;
    }
    pending = true;
  }
  void Observe(int bit, unsigned int q) {
    Require(pending && (bit == 0 || bit == 1) && q >= 1 && q <= 65535);
    row[2] |= (unsigned char)(bit << 1);
    Write(trace, row, sizeof(row));
    const uint16_t qp = (uint16_t)q;
    Write(probability, &qp, 2);
    pending = false; ++count;
  }
  ~Writer() {
    if (!trace) return;
    Require(!pending && channels == (count + 7) / 8);
    Require(std::fclose(trace) == 0);
    Require(std::fclose(channel) == 0);
    Require(std::fclose(probability) == 0);
    std::fprintf(stderr, "CMIX_BITL_TRACE {\"bits\":%llu,\"channels\":%llu,"
                 "\"trace\":\"%s\",\"channel\":\"%s\",\"probability\":\"%s\"}\n",
                 count, channels, names[0], names[1], names[2]);
  }
};
static Writer writer;
}
'''


def rewrite(text, variant=VARIANT):
    if variant != VARIANT:
        raise ValueError("unknown bit trace variant")
    forward = "\n  s.Forward();\n\n  s.skip = override_active ? 1 : 0;"
    observe = "void Observe(int bit) {\n  Head& s = g_head;"
    if text.count(forward) != 1 or text.count(observe) != 1 or "hutter_bit_trace" in text:
        raise ValueError("bit trace patch anchor changed")
    capture = '''
  static_assert(Head::nhid == 32 && Head::nlhid == 32, "trace projection widths");
  hutter_bit_trace::writer.Prepare(s.i, base_p, stage1, n_stage1, m1raw,
      override_active, s.aux_tf, s.aux_n_tf, x + Head::kHid,
      x + Head::kLhid, s.aux_zone);
'''
    return WRITER_CPP + text.replace(forward, capture + forward).replace(
        observe, observe + "\n  hutter_bit_trace::writer.Observe(bit, s.pend_head_p);")


def apply(source, variant):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("bit tracing must not modify pinned upstream")
    path = source / SOURCE
    before = digest(path)
    changed = rewrite(path.read_text(), variant)
    path.write_text(changed)
    return {"name": variant, "source_file": SOURCE, "before_sha256": before,
            "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            "recipe_sha256": digest(Path(__file__)),
            "scope": "Read-only live BITLSTM inputs and integer predictions, bounded to 16000000 model bits. No parameter or training changes; archive identity must be checked separately."}


def inspect_log(log, directory):
    rows = re.findall(r'^CMIX_BITL_TRACE (\{[^\n]+\})$', log.read_text(), re.M)
    if len(rows) != 1:
        raise ValueError("requires exactly one completed bit trace report")
    row = json.loads(rows[0])
    bits, channels = row["bits"], row["channels"]
    if (type(bits) is not int or not 0 < bits <= MAX_BITS
            or type(channels) is not int or channels != (bits + 7) // 8):
        raise ValueError("invalid bit trace counts")
    files = {}
    expected_sizes = {"trace": 28 + 60 * bits, "channel": 28 + 276 * channels, "probability": 2 * bits}
    for role, size in expected_sizes.items():
        name = row[role]
        if not isinstance(name, str) or not re.fullmatch(r"bitl-" + role + r"-\d+\.bin", name):
            raise ValueError("invalid bit trace filename")
        file = directory / name
        if not file.is_file() or file.is_symlink() or file.stat().st_size != size:
            raise ValueError("bit trace length or file type differs")
        files[role] = {"bytes": size, "sha256": digest(file)}
    overrides = ones = 0
    with (directory / row["trace"]).open("rb") as trace, (directory / row["probability"]).open("rb") as probs:
        if trace.read(28) != TRACE_HEADER:
            raise ValueError("bit trace header differs")
        while chunk := trace.read(60 * 65536):
            qvalues = struct.iter_unpack("<H", probs.read(2 * (len(chunk) // 60)))
            for values, (q,) in zip(struct.iter_unpack("<HBB14f", chunk), qvalues):
                bp, flags, reserved, *features = values
                if (not bp or flags > 3 or reserved or not q or not all(map(math.isfinite, features))
                        or (flags & 1 and q != bp)):
                    raise ValueError("invalid bit trace values")
                overrides += flags & 1
                ones += (flags >> 1) & 1
    zones = {}
    with (directory / row["channel"]).open("rb") as stream:
        if stream.read(28) != CHANNEL_HEADER:
            raise ValueError("bit channel header differs")
        while chunk := stream.read(276 * 8192):
            for values in struct.iter_unpack("<69f", chunk):
                zone = values[-1]
                if not all(map(math.isfinite, values)) or not zone.is_integer() or not 0 <= zone <= 3:
                    raise ValueError("invalid bit channel values")
                zones[str(int(zone))] = zones.get(str(int(zone)), 0) + 1
    return {"bits": bits, "channels": channels, "overrides": overrides, "one_bits": ones,
            "channel_zones": zones, "files": files}
