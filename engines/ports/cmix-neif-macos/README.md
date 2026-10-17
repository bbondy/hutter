# Native Mac development experiment

This builds the pinned cmix-neif source as a native ARM64 Mach-O executable with
Apple Clang. It keeps the transformer, weights, online models, model sizes and
dictionary mode. The untouched upstream snapshot remains in `engines/cmix-neif`.
This is a port of our selected competitive baseline, not an exact reproduction
of its submitted Linux executable or an independently verified prize score.

```sh
python3 scripts/native_cmix.py build
python3 scripts/native_cmix.py samples --output build/native-sample-100k
python3 scripts/native_cmix.py bench build/native-sample-100k/articles.ready \
  --output build/native-smoke --timeout 1800 \
  --record native-smoke --note 'Native Mac dictionary-mode baseline' \
  --manifest build/native-sample-100k/manifest.json
```

The sample command requires official `data/enwik8` (`make enwik8` to download).
It checks the corpus hash, takes complete articles from the first page through
the first closing page tag after 100 KB, applies upstream phda9, and verifies
the inverse transformation. The raw and transformed hashes and byte offsets
are recorded. `--target-bytes` selects a larger screening sample.
`--start-offset` selects the first complete article at or after a chosen byte
offset, so a disjoint middle or tail fixture can challenge results from the
opening articles. The manifest records the requested and actual offsets.
Output directories and history IDs must be new. Build dependencies are Apple
command-line tools, Python 3, Git, make and patch. The build downloads the
MIT-licensed [SIMDe](https://github.com/simd-everywhere/simde) v0.8.2 source at
commit `71fd833d9666141edcd1d3c109a80e228303d8d7`; its own license is retained in
the build directory. No Docker or Homebrew compiler installation is required.

`port.patch` and `overlay/` adapt a disposable source copy:

- SIMDe supplies the SSE/AVX2/F16C operations through native ARM code. Explicit
  fused negative multiply-add and multiply-subtract need overrides because
  SIMDe 0.8.2's 256-bit fallbacks otherwise use separate multiply/add operations.
- An attention assembly loop uses the existing per-row intrinsic calculation in
  the same row order. Optional x86 cycle-counter telemetry is disabled.
- Darwin sort callbacks, clock calls and memory growth replace Linux interfaces.
  Huge-page advice and glibc allocator tuning become no-ops.
- `--native-pages N` sets the metadata record count for a development corpus.
  The default remains the release's 243,425 articles. Both encoding and decoding
  need the same value; the benchmark runner takes it from the sample manifest
  and records it with both commands. It is not encoded in the payload. All
  metadata validation stays active. The release timestamp-format boundary of
  87,813 is retained, so small samples use the existing absolute timestamp form.
- PPMd retains its 14,000 MiB logical heap, using demand-zero anonymous memory
  instead of Linux's bounded resident page cache. This can exceed the prize RAM
  limit on larger inputs. Memory measurements cannot validate Linux eligibility.
- Compilation preserves upstream's separate strict and fast floating-point
  groups. It omits x86 flags, glibc forwarders, Linux ELF packing, PGO and LTO.

The supported experiment is `-c dictionary input payload` followed by
`-d dictionary payload restored`, in a private working directory containing the
weight file. The runner supplies that directory and verifies exact restoration.
Do not use this unpacked binary's self-extracting `-e` or no-argument modes.
Raw chunks such as `data/samples/prefix-100k` are not valid inputs to this mode:
the models expect phda9 metadata, not raw Wikipedia XML. The 179-byte smoke
sample also contains bytes excluded from the transformer's frozen alphabet.
Do not disable the transformer or its format guards to hide these failures.
Even a phda9-prepared subset needs its article count supplied through
`--manifest`; the unparameterized release expects the entire enwik9 metadata
block. Its inherited `prof_input/input` fixture fails the current metadata
parser too, so it is not a valid small baseline for this release.

Benchmark records include binary/input/asset hashes, patched source inventory,
compiler, flags, elapsed time, peak RSS and round-trip/repeat checks. Archive
sizes are **payload only**, excluding the external dictionary, weights and
executables. They are useful for native development comparisons, but cannot be
compared directly to a complete Hutter submission score.

Cross-decoding and payload comparisons with the pinned Linux x86-64 build remain
necessary: floating-point/code-generation differences can change this adaptive
coder's stream. A Mac round trip alone cannot establish x86 compatibility.
The first feasibility build used Darwin's libc `rand()`, which differs from
Linux/glibc. New builds use an explicit glibc-compatible generator and include
optional initialization and coder-probability diagnostics. See the
[parity harness](../cmix-neif-parity/README.md) for reproducible checks and saved
results. Matching initialization alone does not establish numerical parity;
the remaining comparison is tracked in
[issue #10](https://github.com/bbondy/hutter/issues/10). Do not interpret native
payloads as reproductions of the published Linux sizes.
Likewise, these samples preserve original article order and omit the census and
comment-index transforms, complete enwik9 reordering, and submission packaging.
They are a first development fixture, not a complete reproduction of the prize
pipeline. Both compression and decompression pretrain on the full dictionary,
so their fixed startup cost can dominate small samples.

The [article-order investigation](../../../docs/benchmarks/2026-10-17/article-order.md)
found that legacy fixtures retain the 71,148-page redirect-block cutoff in both
`redirect_table.h` and `tf1_prompt.h`. Thus small fixtures stay in that block:
ordinary page text is escaped reversibly, and pages after the first get a four-token
`#rd` prompt absent from the full corpus's main-text phase. Those saved samples do not reproduce representative phase boundaries.

New builds share a development-only phase patch with the Linux harness.
`--native-corpus N R -c dictionary input payload` declares N total articles and
R leading redirects; decoding requires the same arguments. A 16-byte development
header stores the counts and rejects mismatches before dictionary pretraining.
The header is included in reported payload bytes. Release defaults (243,425 /
71,148), the pinned upstream snapshot and legacy `--native-pages` remain intact.

`article_order.py prepare` now defaults to corrected mode: identify redirects
using upstream's exact raw XML line prefixes, keep them in source order at the
front, and vary only ordinary articles. The manifest records the prefix count.
The same `--native-corpus N R` arguments reach the standalone phda9 helper and
its inverse; this matters because that helper performs the page-form redirect
transform before the runtime coder sees the data. Manifests retain both sets of
arguments and verification rejects mismatches. Use `--phase-mode legacy` only to reproduce historical fixtures. Existing
`native_cmix.py samples` still produces legacy original-order fixtures.

Corrected-mode logs include read-only `CMIX_CONTEXT` JSON for transformer link
prefixes (including actually fed tokens), redirect/metadata prompts and the byte
model's alias channel. Benchmark verification requires matching encoder/decoder
counters, the expected redirect prompt count and entry into main text whenever
ordinary articles exist. `CMIX_CONTEXT_REPORT=0` suppresses reports for a
telemetry-invariance check; normal benchmark verification requires reports.
Upstream emits page-prefix rows after a separator, so the first page receives
no redirect prompt: the expected count is `max(R - 1, 0)`. Tests cover zero,
mixed and all-redirect preparation prefixes and exact inverse restoration.
The v2 runtime-only correction is rejected because its helper still used the
release cutoff. Both v3 fixtures now pass source/graph/random exact original-byte
restoration and matching context counters. Graph order loses by 6 and 22 payload
bytes. Disabling telemetry produces the identical 119,969-byte screen baseline.
See the saved `benchmarks/article-order/20261017-{screen,holdout}-v3` records.
Do not reinterpret older sizes as if their binaries or phases had changed.

Full-corpus comparison later exposed inherited signed overflow in two XML entity
reductions (`k * 256 + ' '`). Apple Clang left `&lt;`/`&gt;` text unreduced where
the Linux build reduced it. The shared `cmix_preprocess_support.py` patch makes
those two operations explicitly unsigned in disposable Mac/Linux source copies.
The original code triggers the signed-overflow sanitizer; the fix passes at
`-O2` and `-Oz`. A corrected Mac helper reproduces the Linux screen input and
restores its raw XML exactly. The corrected Mac preparation-only tool now also
matches both full upstream coder-stream hashes, as does native Linux. Evidence
is saved under `benchmarks/pipeline/20261017-native-stream-v3` and
`20261017-linux-stream-v1`. This does not establish a full compressed score.

Earlier v1–v3 fixtures remain valid native round trips but use the old entity
representation. Regenerate prepared fixtures and establish fresh baselines
before comparing them with canonical Linux preparation. Treat this as a
portability correction, not a compression-model gain. The untouched upstream
Linux training tool already reproduces both documented full-stream hashes.

The patch and compressor overlays are GPL-3.0-only derivatives of the imported
compressor; all upstream licenses and attribution still apply. See
`engines/cmix-neif/LICENSE`, `NOTICE.md`, `training/ATTRIBUTION.md`, and the root
`LICENSE-SCOPE.md`.
