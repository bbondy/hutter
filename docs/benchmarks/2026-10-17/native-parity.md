# Native / Linux parity investigation

Native Mac and Linux initialize the captured LSTM arrays and indirect-map
offsets identically, but their coder probabilities diverge. Their payload sizes
are just one byte apart on this fixture. That is encouraging for local screening,
but does not establish bitstream compatibility or agreement on candidate ranking.

The portable RNG reproduces 10,000 consecutive glibc outputs for each of seeds
0, 1, 923, 2147483648 and 4294967295. The Linux build still uses its original
libc RNG. See [golden comparisons](../../../benchmarks/parity/20261017-rng-v1/result.json).

Both platforms produce exactly the same 20,621,872-byte initialization snapshot,
SHA-256 `1b4cb3223570a957f7f0c3a89e829194d4006cf521338cecd8d631f206c473e7`.
This snapshot covers the explicitly instrumented arrays, not every byte of the
process address space. The initialization-only runs finish before dictionary
training; their one-byte output is not a compressed result. See the
[initialization record](../../../benchmarks/parity/20261017-initialization-v1/report.json).

The Linux reference image contains `comp9` with the exact expected upstream hash:
`8b07d85f0a374b55688fd08d1a464222f766efbb5bfefc2bc94d6abb201133d7`.
The development comparison uses a separately rebuilt binary, retaining Linux
x86 kernels, bounded paging and the upstream compiler flag groups. Both sides
add the same article-count parameter and optional diagnostics. LLVM rejects
some old PGO counts where instrumentation changes function control flow.

The input is the same 19-article fixture as the earlier native feasibility run:
117,161 raw bytes / 108,927 phda9-prepared bytes. The prepared SHA-256 is
`41c15fd48e12fa85b936132f95aac51223c9296ba9b297020d9171a39c5f7ea0`.
The full dictionary and transformer weights are retained.

With Linux-compatible initialization, the native encoding produces 15,221 bytes
and 473,488 trace events. This differs from the earlier Darwin-RNG result of
15,205 bytes; the initialization correction is not a compression improvement.
The native encode took 195.61 seconds, including 145.17 seconds of dictionary
pretraining. A much smaller fixture will retain this fixed startup cost.

## Complete encoding comparison

| Measurement | Native ARM64 Mac | Linux x86-64, emulated |
|---|---:|---:|
| Prepared input bytes | 108,927 | 108,927 |
| Payload bytes | 15,221 | 15,222 |
| Coder events | 473,488 | 473,488 |
| Encoding wall seconds | 195.61 | 817.36 |

Every event type and input bit matches across the complete traces. There are
272,752 probability differences. The first is zero-based event 190: a normal
coded zero bit with probability 27,039 on Mac and 27,029 on Linux. The first
payload byte difference is offset 29. See the
[full comparison](../../../benchmarks/parity/20261017-probabilities-v1/report.json)
and [trace analysis](../../../benchmarks/parity/20261017-probabilities-v1/trace-analysis.json).
Cross-decoding was deliberately skipped after this failed encoding gate;
interoperability has not been demonstrated.

The Linux development decoder was subsequently tested against **its own**
15,222-byte archive, using the same 19-article manifest and binary. It restored
all 108,927 prepared bytes exactly. Its captured initialization and complete
probability trace matched the Linux encoder, and the recorded validation passed.
The emulated decode took 796.66 wall seconds with maximum resident set size
6,191,896 KiB as reported by `/usr/bin/time -v`. See the
[decoder-only record](../../../benchmarks/parity/20261017-linux-selfdecode-v1/report.json)
and [process log](../../../benchmarks/parity/20261017-linux-selfdecode-v1/decode-process.log).
This is same-platform correctness, not cross-platform archive compatibility.

The native trace-disabled run produced the identical 15,221-byte payload and
passed decompression. Inverse phda9 reconstruction restored all 117,161 raw bytes
with the expected hash. Its compression/decompression took 205.94 / 202.43
seconds with peak RSS about 5.76 GB. See its
[record](../../../benchmarks/runs/20261017-native-linux-rng-trace-off/results.jsonl)
and [verification](../../../benchmarks/runs/20261017-native-linux-rng-trace-off/verification.json).
These timings are exploratory: single trials, with other work running
concurrently. The Linux encode overlapped native checks and a diagnostic build.

Neither sample payload sizes nor emulated Linux timings establish a full enwik9
score or prize eligibility. Payload sizes exclude dictionary, weights and
executables. See the [harness instructions](../../../engines/ports/cmix-neif-parity/README.md).

Builds began before the harness commit; records retain the original HEAD and
exact source inventories. The implementation is committed as `3e6e73c`.

## First numerical differences

The bounded diagnostic rebuilds reproduce the first 256 probability events of
their respective ordinary builds exactly. Thus the additional probes preserve
the prefix being investigated. See the
[diagnostic report](../../../benchmarks/parity/20261017-numerical-prefix-v1/report.json)
and [stage analysis](../../../benchmarks/parity/20261017-numerical-prefix-v1/stage-analysis.json).

| First differing recorded stage | Event | Native value | Linux value |
|---|---:|---:|---:|
| Model input 556 | 0 | -5.96046448e-8 | 0 |
| LSTM value before normalization, index 3 | 8 | 1.15185272694 | 1.15185260773 |
| LSTM inverse normalization | 8 | 0.97465556860 | 0.97465544939 |
| Mixer bank output, index 7 | 10 | -3.30934054e-5 | -3.24112552e-5 |
| Predictor probability | 190 | 0.41259232163 | 0.41243973374 |

Model input 556 is the neutral FXCM logit plus the ID-exclusion adjustment.
The neutral term comes from `Sigmoid::LogitBase(0.5f)`. The
[native disassembly](../../../benchmarks/parity/20261017-numerical-prefix-v1/native-logitbase.asm)
shows that fast-math compilation implements `(index + 0.5f) / 100001` using a
rounded reciprocal and fused multiply-add. At index 50,000, that produces
0.4999999701976776; subsequent float division and log give the observed
-5.96046448e-8 offset, instead of the exact neutral value zero. This gives a
specific arithmetic calculation to investigate, beyond the resolved RNG issue.
The later LSTM differences may have additional causes; fixing this one term
has not been tested and would not by itself establish compatibility.

The earlier initialization gate deliberately captured randomized LSTM arrays
and indirect offsets. It did **not** compare all derived floating-point tables.
Extend that coverage to the neutral logit and FXCM/auxiliary tables in the next
numerical investigation. Do not read its passing result as proof that the entire
predictor starts identically.

## Next steps toward the prize

1. Keep the pinned Linux implementation as the authoritative score baseline.
   Its development decoder passed the first fixture. Reproduce the complete
   enwik9 pipeline and packaged score on native x86-64 Linux, with runtime and
   peak-memory checks.
2. Evaluate larger and held-out article fixtures on both platforms. A one-byte
   difference on one small fixture does not demonstrate that a model change's
   gains transfer. Confirm every promising Mac experiment against Linux.
3. Use the first numerical divergence to estimate the cost of exact ARM parity.
   Avoid making a complete floating-point portability rewrite a prerequisite
   for compression research. The existing Linux environment can run authoritative
   experiments while Mac provides faster preliminary screening.
4. Keep saving failures and improvements with input/source/binary/asset hashes.
   Preserve full dictionary pretraining in comparisons; smaller files alone do
   not remove the roughly 145-second native startup cost measured here.
