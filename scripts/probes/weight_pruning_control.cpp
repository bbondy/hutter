// Compare the real kernels with zeroed full-width rows and removed rows.
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
  if (argc != 4) return 2;
  OptModel masked, pruned;
  masked.load(argv[1]);
  pruned.load(argv[2]);
  FILE* map = std::fopen(argv[3], "r");
  if (!map) return 2;
  unsigned long long checked = 0;
  for (int layer = 0; layer < OptModel::NL; ++layer) {
    const auto& a = masked.mlp[layer];
    const auto& b = pruned.mlp[layer];
    int width, count, keep[768];
    bool retained[768] = {};
    if (std::fscanf(map, "%d %d", &width, &count) != 2 ||
        width < 1 || width > 768 || count < 1 || count >= width ||
        width != a.down.d_in || count != b.down.d_in ||
        width != a.up.m.d_out || count != b.up.m.d_out ||
        a.up.s_act != b.up.s_act || a.down_s_act != b.down_s_act) return 3;
    for (int i = 0; i < count; ++i) {
      if (std::fscanf(map, "%d", &keep[i]) != 1 || keep[i] < 0 || keep[i] >= width ||
          (i && keep[i] <= keep[i - 1])) return 3;
      retained[keep[i]] = true;
    }
    for (int trial = 0; trial < 1024; ++trial) {
      alignas(64) uint8_t input[256] = {}, qa[768] = {}, qb[768] = {};
      alignas(64) uint16_t ia[832] = {}, ib[832] = {};
      alignas(64) float as[192], ad[192], bs[192], bd[192];
      for (int i = 0; i < 192; ++i) {
        input[i] = trial == 0 ? 0 : trial == 1 ? 128 : trial == 2 ? 255 :
                   trial == 3 ? (i & 1 ? 255 : 0) : next() & 255;
        as[i] = ad[i] = bs[i] = bd[i] = float(int(next() & 4095) - 2048) / 16.0f;
      }
      const int na = qgemv_relu2q(a.up.m, input, a.down_s_act, qa, ia);
      const int nb = qgemv_relu2q(b.up.m, input, b.down_s_act, qb, ib);
      if (na != nb) {
        std::fprintf(stderr, "nonzero counts differ layer %d trial %d\n", layer, trial);
        return 4;
      }
      for (int i = 0; i < count; ++i)
        if (qa[keep[i]] != qb[i]) return 5;
      for (int i = 0; i < width; ++i)
        if (!retained[i] && qa[i]) return 6;
      // Force both sparse and dense routes, including width-tail handling.
      qsparse4_add(a.down, qa, ia, na, as);
      qsparse4_dense_add(a.down, qa, ad);
      qsparse4_add(b.down, qb, ib, nb, bs);
      qsparse4_dense_add(b.down, qb, bd);
      if (std::memcmp(as, ad, sizeof(as)) || std::memcmp(as, bs, sizeof(as)) ||
          std::memcmp(as, bd, sizeof(as))) {
        std::fprintf(stderr, "output bits differ layer %d trial %d\n", layer, trial);
        return 7;
      }
      ++checked;
    }
  }
  char extra;
  if (std::fscanf(map, " %c", &extra) != EOF) return 3;
  std::fclose(map);
  std::fprintf(stderr, "{\"passed\":true,\"layers\":16,\"cases_per_layer\":1024,"
              "\"block_cases\":%llu,\"retained_activations_exact\":true,"
              "\"sparse_and_dense_checked\":true}\n", checked);
  return 0;
}
