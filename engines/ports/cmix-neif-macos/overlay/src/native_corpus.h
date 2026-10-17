// GPL-3.0-only. Development configuration; release defaults stay unchanged.
#pragma once
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <istream>
#include <ostream>

namespace native_corpus {
inline unsigned int page_count = 243425;
inline unsigned int redirect_count = 71148;
inline bool framed = false;
inline unsigned int PageCount() { return page_count; }
inline unsigned int RedirectCount() { return redirect_count; }
inline bool Telemetry() {
  const char* value = std::getenv("CMIX_CONTEXT_REPORT");
  return framed && (!value || std::strcmp(value, "0"));
}
inline void Header(unsigned char* h) {
  std::memcpy(h, "HUTDEV2\0", 8);
  for (int i = 0; i < 4; ++i) {
    h[8 + i] = (page_count >> (8 * i)) & 255;
    h[12 + i] = (redirect_count >> (8 * i)) & 255;
  }
}
inline bool WriteHeader(std::ostream* out) {
  if (framed) {
    unsigned char h[16]; Header(h);
    out->write(reinterpret_cast<const char*>(h), sizeof(h));
  }
  return bool(*out);
}
inline bool ReadHeader(std::istream* in) {
  if (framed) {
    unsigned char h[16], expected[16]; Header(expected);
    in->read(reinterpret_cast<char*>(h), sizeof(h));
    if (!*in || std::memcmp(h, expected, sizeof(h))) return false;
  }
  return bool(*in);
}
inline bool Number(const char* text, unsigned int* result) {
  if (!*text || std::strspn(text, "0123456789") != std::strlen(text)) return false;
  errno = 0;
  unsigned long n = std::strtoul(text, nullptr, 10);
  if (errno || n > 243425) return false;
  *result = static_cast<unsigned int>(n);
  return true;
}
// --native-pages reproduces old, unframed fixtures with the 71148 cutoff.
// --native-corpus N R is explicit on BOTH sides and stores N/R in the archive.
// Check the frame before weight extraction or expensive dictionary pretraining.
inline bool Configure(int* argc, char** argv) {
  const bool legacy = *argc > 1 && !std::strcmp(argv[1], "--native-pages");
  framed = *argc > 1 && !std::strcmp(argv[1], "--native-corpus");
  if (legacy || framed) {
    const int skip = framed ? 3 : 2;
    if (*argc != 5 + skip || !Number(argv[2], &page_count) || !page_count ||
        (framed && (!Number(argv[3], &redirect_count) || redirect_count > page_count)) ||
        (std::strcmp(argv[1 + skip], "-c") && std::strcmp(argv[1 + skip], "-d"))) {
      std::fprintf(stderr, "development mode requires dictionary -c/-d, pages 1..243425, redirects 0..pages\n");
      return false;
    }
    *argc -= skip;
    for (int i = 1; i < *argc; ++i) argv[i] = argv[i + skip];
    argv[*argc] = nullptr;
    std::fprintf(stderr, "native development corpus: %u articles, %u redirect prefix, frame=%d\n",
                 page_count, redirect_count, int(framed));
  }
  if (*argc == 5 && (!std::strcmp(argv[1], "-d") || !std::strcmp(argv[1], "-D"))) {
    FILE* in = std::fopen(argv[3], "rb");
    if (!in) return false;
    unsigned char h[16] = {}, expected[16]; Header(expected);
    const size_t n = std::fread(h, 1, sizeof(h), in);
    std::fclose(in);
    const bool magic = n >= 8 && !std::memcmp(h, expected, 8);
    if ((framed && (n != sizeof(h) || std::memcmp(h, expected, sizeof(h)))) ||
        (!framed && magic)) {
      std::fprintf(stderr, "development corpus header mismatch: use the encoder's --native-corpus N R\n");
      return false;
    }
  }
  return true;
}
}
