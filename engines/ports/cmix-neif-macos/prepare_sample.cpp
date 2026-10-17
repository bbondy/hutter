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
  const bool configured = argc > 1 && !strcmp(argv[1], "--native-corpus");
  if (configured) {
    if (argc != 7 || !native_corpus::Number(argv[2], &native_corpus::page_count) ||
        !native_corpus::page_count || !native_corpus::Number(argv[3], &native_corpus::redirect_count) ||
        native_corpus::redirect_count > native_corpus::page_count) {
      fprintf(stderr, "helper requires --native-corpus N R with pages 1..243425, redirects 0..pages\n");
      return 2;
    }
    argc -= 3;
    for (int i = 1; i < argc; ++i) argv[i] = argv[i + 3];
    argv[argc] = nullptr;
  }
  if (argc != 4 || (strcmp(argv[1], "encode") && strcmp(argv[1], "decode"))) {
    fprintf(stderr, "usage: prepare-sample [--native-corpus N R] encode|decode input output\n");
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
  const long long pages = !strcmp(argv[1], "encode") ? g1_seiten : g1_rc_dseiten;
  bool failed = ferror(in) || ferror(out);
  if (configured && pages != (long long)native_corpus::PageCount()) {
    fprintf(stderr, "helper page count differs: %lld observed, %u declared\n", pages, native_corpus::PageCount());
    failed = true;
  }
  if (fclose(in)) failed = true;
  if (fclose(out)) failed = true;
  return failed ? 1 : 0;
}
