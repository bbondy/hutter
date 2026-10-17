// GPL-3.0-only. Development configuration for the imported metadata codec.
#pragma once
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace native_corpus {
inline unsigned int page_count = 243425;
inline unsigned int PageCount() { return page_count; }

// An explicit out-of-band development parameter, needed on both sides.
// The normal entry point retains the full enwik9 metadata count.
inline bool Configure(int* argc, char** argv) {
  if (*argc < 2 || strcmp(argv[1], "--native-pages")) return true;
  if (*argc < 4) return false;
  char* end = nullptr;
  errno = 0;
  unsigned long n = strtoul(argv[2], &end, 10);
  if (errno || !*argv[2] || *end || n < 1 || n > 243425 ||
      (strcmp(argv[3], "-c") && strcmp(argv[3], "-d"))) {
    fprintf(stderr, "--native-pages requires 1..243425 and dictionary -c/-d mode\n");
    return false;
  }
  page_count = (unsigned int)n;
  fprintf(stderr, "native development metadata: %u articles\n", page_count);
  *argc -= 2;
  for (int i = 1; i < *argc; ++i) argv[i] = argv[i + 2];
  argv[*argc] = nullptr;
  return true;
}
}
