# Native / Linux parity checks

This harness compares the ARM64 Mac port with an x86-64 Linux development build
from the same pinned source. Docker runs the Linux reference only; native builds
and ordinary Mac experiments do not require it. Docker on ARM emulates x86, so
its timings cannot establish prize performance eligibility.

The Linux image must contain the published `comp9` at `/opt/cmix-build/comp9`,
Python 3, LLVM 18, make and `/usr/bin/time`. The harness verifies the published
binary's SHA-256, then pins the local image ID. Our development comparison binary
is rebuilt with the original x86 kernels, paging and upstream PGO/LTO/FP flags.
It adds the same article-count parameter as the Mac port plus optional tracing.
Instrumentation changes control flow, so some inherited PGO counts are rejected
by LLVM. This binary is not the byte-identical published executable.

```sh
python3 scripts/cmix_parity.py rng --output build/parity-rng
python3 scripts/native_cmix.py build --output build/native-parity
python3 scripts/cmix_parity.py build-linux --output build/linux-parity
python3 scripts/native_cmix.py samples --build build/native-parity \
  --output build/parity-sample
python3 scripts/cmix_parity.py compare \
  --native build/native-parity --linux build/linux-parity \
  --input build/parity-sample/articles.ready \
  --manifest build/parity-sample/manifest.json \
  --output build/parity-init --init-only --record parity-init
python3 scripts/cmix_parity.py compare \
  --native build/native-parity --linux build/linux-parity \
  --input build/parity-sample/articles.ready \
  --manifest build/parity-sample/manifest.json \
  --output build/parity-full --record parity-full

# A failed cross-platform encoding comparison can still validate either
# platform's decoder against its own completed archive without recompression:
python3 scripts/cmix_parity.py decode \
  --platform linux --build build/linux-parity --source-run build/parity-full \
  --input build/parity-sample/articles.ready \
  --manifest build/parity-sample/manifest.json \
  --output build/linux-self-decode --record linux-self-decode
```

Use `--context NAME --image IMAGE` before the subcommand to override the default
`colima-hutter` context and `hutter-cmix-neif:baseline` image. All output directories
and record IDs must be new. Each process has a private working directory. The
default per-process timeout is 7,200 seconds; set `compare --timeout` as needed.

The successive gates are:

1. Explicit portable RNG matches Linux libc on 10,000 draws each for five seeds,
   including seed 923 and unsigned edge cases. Linux itself still uses libc.
2. Initialized LSTM arrays and indirect-map offsets are byte-identical. The
   `--init-only` gate stops before dictionary pretraining or any coding.
3. Both encoders consume the identical prepared fixture and assets. Compare all
   final integer coder probabilities, forced/known/raw bit events, and payload
   bytes. First-difference byte/record offsets are saved. A mismatch fails this
   gate and skips decoding until the numerical divergence is resolved.
4. When encodings match, both platforms decode both payloads. All four outputs
   must match the input hash; decoder event traces must match their encoder.

The trace validator rejects absent completion markers, empty initialization,
truncation and incorrect event counts. `initial.bin` contains the recorded raw
arrays (both tested platforms are little endian); `initial.jsonl` indexes their
lengths and FNV hashes. `probabilities.bin` has 8-byte little-endian records:
kind, bit, two reserved zero bytes, and a u32 probability. Kinds 0/1/2/3 mean
normal/forced/raw/known. Known and forced bits carry a zero probability marker.
This observes coding, not every internal prediction during dictionary training.
Completed full paired encodings also save `trace-analysis.json`: event counts,
input/type identity hashes, probability mismatch count and first difference,
plus each payload size and elapsed time. Unequal or incomplete trace lengths are
reported as an analysis error in the main report without discarding the failed
comparison.

For a bounded numerical investigation, rebuild both platforms with current
support files and add `compare --event-limit 256`. This retains full dictionary
pretraining, captures model inputs, mixer outputs and LSTM normalization stages,
then stops after 256 coder events. The report identifies the first differing
stage, event and float index. It is explicitly a diagnostic prefix: it produces
no valid archive and cannot pass the full encoding validator. Keep these runs
under separate output directories and record IDs. Check that their probability
prefixes match the ordinary builds before interpreting the added instrumentation.

`--record ID` saves provenance, hashes, outcomes and text diagnostics under
`benchmarks/parity/ID`. Large binaries, state dumps and event streams remain in
the local build directory. Failed completed comparisons are retained too. A
partially interrupted run keeps its phase records in its output directory.
The decoder-only command verifies the saved encoder archive and trace hashes,
then compares restored bytes, initial state and every decoder event against its
own encoder. It does not imply cross-platform decoding when encodings differ.

A fixture pass would establish compatibility only for that fixture. Before
claiming a comparable competitive baseline, test larger and held-out article
sets, confirm tracing does not alter outputs, and reproduce the complete enwik9
pipeline with the unmodified submission on native x86-64 Linux. Account for the
archive, executable and arguments, plus measured runtime and peak memory.

The C++ support and corpus patch are GPL-3.0-only; independent Python tools use
the repository MIT license. Upstream source and notices remain unchanged.
