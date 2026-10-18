// Exercise the real quantized MLP kernels on original and permuted containers.
// This probe calls the pinned cmix-neif/fx2 kernels; it does not reimplement them.
#include "tf1/opt/arena_build.h"
#include "tf1/opt/qmat_dense.h"
#include "tf1/opt/qmat_sparse.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

using namespace fx2::opt;

static uint32_t state = 0x92f375abu;
static uint32_t next() {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: weight-permutation-probe ORIGINAL CANDIDATE\n");
    return 2;
  }
  OptModel original, candidate;
  original.load(argv[1]);
  candidate.load(argv[2]);
  unsigned long long checked = 0;
  for (int layer = 0; layer < OptModel::NL; ++layer) {
    const auto& a = original.mlp[layer];
    const auto& b = candidate.mlp[layer];
    if (a.down.d_in != b.down.d_in || a.up.s_act != b.up.s_act ||
        a.down_s_act != b.down_s_act) return 3;
    for (int trial = 0; trial < 1024; ++trial) {
      alignas(64) uint8_t input[256] = {};
      alignas(64) uint8_t qa[768] = {}, qb[768] = {};
      alignas(64) uint16_t ia[832] = {}, ib[832] = {};
      alignas(64) float as[192], ad[192], bs[192], bd[192];
      for (int i = 0; i < 192; ++i) {
        // Biased-u8 extremes, centered zero, alternating extremes, then random.
        input[i] = trial == 0 ? 0 : trial == 1 ? 128 : trial == 2 ? 255 :
                   trial == 3 ? (i & 1 ? 255 : 0) : next() & 255;
        as[i] = ad[i] = bs[i] = bd[i] = float(int(next() & 4095) - 2048) / 16.0f;
      }
      const int na = qgemv_relu2q(a.up.m, input, a.down_s_act, qa, ia);
      const int nb = qgemv_relu2q(b.up.m, input, b.down_s_act, qb, ib);
      if (na != nb) {
        std::fprintf(stderr, "nonzero count differs at layer %d trial %d\n", layer, trial);
        return 4;
      }
      // Force both routes, even if the production density switch picks one.
      qsparse4_add(a.down, qa, ia, na, as);
      qsparse4_dense_add(a.down, qa, ad);
      qsparse4_add(b.down, qb, ib, nb, bs);
      qsparse4_dense_add(b.down, qb, bd);
      if (std::memcmp(as, ad, sizeof(as)) || std::memcmp(as, bs, sizeof(as)) ||
          std::memcmp(as, bd, sizeof(as))) {
        std::fprintf(stderr, "output bits differ at layer %d trial %d\n", layer, trial);
        return 5;
      }
      ++checked;
    }
  }
  std::fprintf(stderr, "{\"passed\":true,\"layers\":16,\"cases_per_layer\":1024,"
              "\"block_cases\":%llu,\"sparse_and_dense_checked\":true}\n", checked);
  return 0;
}
