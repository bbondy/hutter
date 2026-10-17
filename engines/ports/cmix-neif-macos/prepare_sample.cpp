// GPL-3.0-only: development driver for the imported phda9 preprocessor.
// See cmix-neif's LICENSE and attribution notices for the included code.
#include <cstdint>
#include <cstring>
#include <unistd.h>
#include <string>
#include <vector>
#include <algorithm>
#include "readalike_prepr/phda9_preprocess.h"

int main(int argc, char** argv) {
  if (argc != 4 || (strcmp(argv[1], "encode") && strcmp(argv[1], "decode"))) {
    fprintf(stderr, "usage: prepare-sample encode|decode input output\n");
    return 2;
  }
  FILE* in = fopen(argv[2], "rb");
  if (!in) { perror(argv[2]); return 1; }
  FILE* out = fopen(argv[3], "wb");
  if (!out) { perror(argv[3]); fclose(in); return 1; }
  if (!strcmp(argv[1], "encode")) {
    encode_txt_wit(in, out);
  } else {
    fseek(in, 0, SEEK_END);
    U64 n = ftell(in);
    rewind(in);
    decode_txt_wit(in, out, n);
  }
  bool failed = ferror(in) || ferror(out);
  if (fclose(in)) failed = true;
  if (fclose(out)) failed = true;
  return failed ? 1 : 0;
}
