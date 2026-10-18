"""Read-only MLP activation telemetry on disposable development builds."""
import hashlib
import json
from pathlib import Path
import re

from competitive import ENGINE
from make_samples import digest

SOURCE = "src/tf1/opt/model_opt.cpp"
VARIANT = "mlp"
ANCHOR = "      nnz = qgemv_relu2q(mm.up.m, q5, mm.down_s_act, q768, idx768);"
COUNTER_CPP = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
namespace hutter_mlp_activity {
struct Counters {
  unsigned long long calls[16] = {}, count[16][768] = {},
      sum[16][768] = {}, sumsq[16][768] = {};
  int widths[16] = {};
  void Record(int layer, int width, const uint8_t* q, const uint16_t* idx, int nnz) {
    if (layer < 0 || layer >= 16 || width < 1 || width > 768 || nnz < 0 || nnz > width ||
        (widths[layer] && widths[layer] != width)) std::abort();
    widths[layer] = width;
    ++calls[layer];
    for (int j = 0; j < nnz; ++j) {
      const int i = idx[j];
      if (i >= width || (j && idx[j - 1] >= i) || !q[i] || q[i] > 127) std::abort();
      ++count[layer][i];
      sum[layer][i] += q[i];
      sumsq[layer][i] += static_cast<unsigned int>(q[i]) * q[i];
    }
  }
  ~Counters() {
    for (int layer = 0; layer < 16; ++layer) {
      std::fprintf(stderr, "CMIX_MLP_ACTIVITY {\"layer\":%d,\"width\":%d,\"calls\":%llu",
                   layer, widths[layer], calls[layer]);
      const char* names[] = {"count", "sum", "sumsq"};
      const unsigned long long* fields[] = {count[layer], sum[layer], sumsq[layer]};
      for (int field = 0; field < 3; ++field) {
        std::fprintf(stderr, ",\"%s\":[", names[field]);
        for (int i = 0; i < widths[layer]; ++i)
          std::fprintf(stderr, "%s%llu", i ? "," : "", fields[field][i]);
        std::fputc(']', stderr);
      }
      std::fputs("}\n", stderr);
    }
  }
};
static Counters counters;
}
'''


def rewrite(text, variant=VARIANT):
    if variant != VARIANT:
        raise ValueError("unknown activation telemetry variant")
    if text.count(ANCHOR) != 1 or "hutter_mlp_activity" in text:
        raise ValueError("activation telemetry patch anchor changed")
    return COUNTER_CPP + text.replace(ANCHOR, ANCHOR +
        "\n      hutter_mlp_activity::counters.Record(l, mm.down.d_in, q768, idx768, nnz);")


def apply(source, variant):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("activation telemetry must not modify pinned upstream")
    path = source / SOURCE
    before = digest(path)
    changed = rewrite(path.read_text(), variant)
    path.write_text(changed)
    return {"name": variant, "source_file": SOURCE, "before_sha256": before,
            "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            "recipe_sha256": digest(Path(__file__)),
            "scope": "Integer counts and first/second moments of actual quantized MLP activations; no model parameter changes. Archive identity and matching encoder/decoder counters are required separately."}


def parse_log(path):
    rows = [json.loads(s) for s in re.findall(r'^CMIX_MLP_ACTIVITY (\{[^\n]+\})$', path.read_text(), re.M)]
    if len(rows) != 16 or [r["layer"] for r in rows] != list(range(16)):
        raise ValueError("missing, repeated or reordered activation layers")
    for row in rows:
        width, calls = row["width"], row["calls"]
        if type(width) is not int or not 1 <= width <= 768 or type(calls) is not int or calls <= 0:
            raise ValueError("invalid activation width or call count")
        if any(len(row[k]) != width for k in ("count", "sum", "sumsq")):
            raise ValueError("incomplete activation vectors")
        for n, s, s2 in zip(row["count"], row["sum"], row["sumsq"]):
            if (any(type(x) is not int for x in (n, s, s2)) or not 0 <= n <= calls
                    or not n <= s <= 127 * n or not s <= s2 <= 127 * s or s * s > n * s2):
                raise ValueError("inconsistent activation moments")
    return rows
