#include "linux_random.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
int main(int argc, char** argv) {
  if (argc != 4) return 2;
  unsigned seed = static_cast<unsigned>(strtoull(argv[2], nullptr, 10));
  unsigned count = static_cast<unsigned>(strtoul(argv[3], nullptr, 10));
  bool system = strcmp(argv[1], "system") == 0;
  if (system) srand(seed); else linux_random::Seed(seed);
  for (unsigned i = 0; i < count; ++i) {
    unsigned v = system ? rand() : linux_random::Next();
    unsigned char b[4];
    for (unsigned j = 0; j < 4; ++j) b[j] = (v >> (j*8)) & 255;
    if (fwrite(b, 1, 4, stdout) != 4) return 1;
  }
  return 0;
}
