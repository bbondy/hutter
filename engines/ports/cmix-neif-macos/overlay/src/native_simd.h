#pragma once
#define SIMDE_ENABLE_NATIVE_ALIASES
#include <simde/x86/avx2.h>
#include <simde/x86/fma.h>
#include <simde/x86/f16c.h>

#define _MM_FROUND_NO_EXC SIMDE_MM_FROUND_NO_EXC
typedef simde__m256i __m256i_u __attribute__((aligned(1), may_alias));

// SIMDe 0.8.2 implements these 256-bit fallbacks as separate mul/add.
// Preserve the explicit fused operation requested by the original kernels.
inline __m256 native_fnmadd(__m256 a,__m256 b,__m256 c) {
 return simde_mm256_fmadd_ps(simde_mm256_xor_ps(a,simde_mm256_set1_ps(-0.0f)),b,c);
}
inline __m256 native_fmsub(__m256 a,__m256 b,__m256 c) {
 return simde_mm256_fmadd_ps(a,b,simde_mm256_xor_ps(c,simde_mm256_set1_ps(-0.0f)));
}
#undef _mm256_fnmadd_ps
#define _mm256_fnmadd_ps(a,b,c) native_fnmadd(a,b,c)
#undef _mm256_fmsub_ps
#define _mm256_fmsub_ps(a,b,c) native_fmsub(a,b,c)
