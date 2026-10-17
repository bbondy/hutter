// GPL-3.0-only. Optional diagnostics; never substitutes predictions or models.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <string>
namespace parity_trace {
inline const char* directory = getenv("CMIX_PARITY_DIR");
inline FILE* probabilities = nullptr;
inline FILE* initial = nullptr;
inline FILE* initial_bytes = nullptr;
inline unsigned long long events = 0;
inline bool Enabled() { return directory && directory[0]; }
inline FILE* Open(const char* name) {
  std::string path = std::string(directory) + "/" + name;
  FILE* f = fopen(path.c_str(), "wb");
  if (!f) { perror(path.c_str()); exit(3); }
  return f;
}
inline void Write(FILE* f, const void* p, size_t n) {
  if (fwrite(p, 1, n, f) != n) { perror("parity trace write"); exit(3); }
}
inline void State(const char* label, const void* p, size_t n) {
  if (!Enabled()) return;
  if (!initial) { initial = Open("initial.jsonl"); initial_bytes = Open("initial.bin"); }
  const unsigned char* b = static_cast<const unsigned char*>(p);
  uint64_t h = 14695981039346656037ULL;
  for (size_t i=0;i<n;++i) h = (h ^ b[i]) * 1099511628211ULL;
  fprintf(initial, "{\"name\":\"%s\",\"bytes\":%zu,\"fnv64\":\"%016llx\"}\n", label,n,(unsigned long long)h);
  Write(initial_bytes,p,n);
  fflush(initial); fflush(initial_bytes);
}
inline void Ready() {
  if (!Enabled()) return;
  FILE* f = Open("initial.complete"); fclose(f);
  if (getenv("CMIX_PARITY_INIT_ONLY")) exit(0);
}
// Fixed 8-byte LE records: kind (normal=0, forced=1, raw=2, known=3),
// bit, two reserved bytes, final integer arithmetic-coder probability (u32).
inline void Event(unsigned kind, unsigned bit, unsigned p) {
  if (!Enabled()) return;
  if (!probabilities) probabilities = Open("probabilities.bin");
  unsigned char b[8] = {(unsigned char)kind,(unsigned char)bit,0,0,0,0,0,0};
  for (unsigned j=0;j<4;++j) b[4+j]=(p>>(8*j))&255;
  Write(probabilities,b,8); ++events;
}
inline void Finish() {
  if (!Enabled()) return;
  if (probabilities && fflush(probabilities)) { perror("parity flush"); exit(3); }
  FILE* f=Open("trace.complete");
  fprintf(f,"%llu\n",events); fclose(f);
}
}
