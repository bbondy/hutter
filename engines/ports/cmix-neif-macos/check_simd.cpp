// Regression probes for rounding needed by the arithmetic coder's predictor.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include "native_simd.h"

static bool equal_lanes(__m256 v, float expected) {
  alignas(32) float lanes[8];
  _mm256_store_ps(lanes, v);
  for (float lane : lanes) {
    uint32_t actual_bits, expected_bits;
    memcpy(&actual_bits, &lane, 4);
    memcpy(&expected_bits, &expected, 4);
    if (actual_bits != expected_bits) return false;
  }
  return true;
}

int main() {
  // (1 + 2^-23)(1 - 2^-23) = 1 - 2^-46. A separately rounded
  // multiplication loses the residual. FMA must retain it exactly.
  const __m256 a = _mm256_set1_ps(0x1.000002p0f);
  const __m256 b = _mm256_set1_ps(0x1.fffffcp-1f);
  const __m256 one = _mm256_set1_ps(1.0f);
  bool ok = equal_lanes(_mm256_fmadd_ps(a, b, _mm256_set1_ps(-1.0f)), -0x1p-46f);
  ok &= equal_lanes(_mm256_fnmadd_ps(a, b, one), 0x1p-46f);
  ok &= equal_lanes(_mm256_fmsub_ps(a, b, one), -0x1p-46f);
  alignas(32) float ties[] = {0.5f, 1.5f, 2.5f, 3.5f, -0.5f, -1.5f, -2.5f, -3.5f};
  alignas(32) int32_t actual[8];
  const int32_t expected[] = {0, 2, 2, 4, 0, -2, -2, -4};
  _mm256_store_si256((__m256i*)actual, _mm256_cvtps_epi32(_mm256_load_ps(ties)));
  ok &= memcmp(actual, expected, sizeof(actual)) == 0;
  if (!ok) fprintf(stderr, "native SIMD rounding check failed\n");
  return ok ? 0 : 1;
}
