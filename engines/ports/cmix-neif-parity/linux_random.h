// GPL-3.0-only. Explicit implementation of the glibc default rand sequence.
// Arithmetic specification: degree-31 additive generator, lag 3, discard low
// bit; Park-Miller seed expansion followed by 310 warm-up draws. No libc state.
#pragma once
#include <cstdint>
namespace linux_random {
inline uint32_t state[31] = {};
inline unsigned front = 3, rear = 0;
inline int Next() {
  uint32_t sum = state[front] + state[rear];
  state[front] = sum;
  if (++front == 31) front = 0;
  if (++rear == 31) rear = 0;
  return static_cast<int>(sum >> 1);
}
inline void Seed(unsigned seed) {
  if (seed == 0) seed = 1;
  state[0] = seed;
  int64_t word = static_cast<int32_t>(seed);
  for (unsigned i = 1; i < 31; ++i) {
    word = (16807 * word) % 2147483647;
    if (word < 0) word += 2147483647;
    state[i] = static_cast<uint32_t>(word);
  }
  front = 3; rear = 0;
  for (unsigned i = 0; i < 310; ++i) Next();
}
}
