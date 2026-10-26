# Hutter Prize research plan — 2026-10-17

**Decision after review:** winning is the primary objective. We have selected
cmix-neif 1.0 as the competitive implementation and vendored its pinned source
into this repo. See [engine setup and reproduction](../engines/README.md).
The original analysis below remains useful context, but reproducing the upstream
baseline now takes priority over making the Rust implementation competitive.

The [October 14 LTCB listing](https://www.mattmahoney.net/dc/text.html) now ranks
[Ex-Girlfriend 1.0](https://github.com/rlanday/ex-girlfriend/tree/v1.0) above
cmix-neif by 135,106 self-extracting-archive bytes, but labels it **not
eligible** for the Hutter Prize. Its GPL-3.0 source is pinned at
`e923faec085a93d24bf519986ee2881497e97934` for read-only local audit.
The release reports about 61/67 hours to encode/decode and nearly 10 GiB RSS
on its measured host. Keep cmix-neif as the exactly reproduced control; test
the derivative's page-id and timestamp forecasts as separate low-overhead
hypotheses before considering its more costly online predictor or larger maps.
The [official prize page](https://prize.hutter1.net/) still displays its
accepted 100,424,672-byte record, distinct from newer benchmark listings and
pending submissions. Full eligibility remains a measured, judged question.
If the pending 95,914,051-byte cmix-neif package becomes the accepted record
with no intervening award, the next 1% prize threshold would be at most
94,954,910 bytes. Our small fixture gains do not demonstrate that margin.
An [isolated E1 comparison](../benchmarks/metadata) restores exactly and
saves 13 and 16 payload bytes on the screen and disjoint Mac fixtures, while
its unpacked development executable grows 4,112 bytes. Native Linux
[release accounting](../benchmarks/metadata/20261023-e1-release-v1) adds
2,094 bytes of measured components. A full-stream payload gain would need
to exceed that cost before treating E1 as a useful prize candidate;
[issue #18](https://github.com/bbondy/hutter/issues/18) tracks the focused
metadata work.

## Current evidence and next moves

The initial Rust assessment below is historical context. The competitive track
has since established a stronger reference and a repeatable research loop:

| Work | Saved finding | Decision |
| --- | --- | --- |
| [Native Linux release](../benchmarks/weights/20261017-linux-packages-gcc13-v1) | Exact published `comp9`: 4,000,689 bytes, matching SHA-256, built on Ubuntu without Docker. Extra GCC 14 headers had changed the first build. | Use this package as the release control; full compression and independent SFX decoding remain unverified. |
| [Canonical preprocessing](../benchmarks/pipeline/20261017-native-stream-v3) | An inherited signed-overflow expression changed Mac entity encodings despite successful raw round trips. Explicit unsigned reduction reproduces both upstream full-stream hashes on Mac and Linux. | Use corrected frozen inputs; retain older representations separately. |
| [Order](../benchmarks/article-order/20261017-projected-screen-v2), [context](../benchmarks/model-variants/20261017-linux-screen-v2), [depth](../benchmarks/model-variants/20261017-depth-linux-screen-v1) | No proposed ordering wins both Mac fixtures; reduced context and tested depth settings lose both native Linux fixtures. | Keep upstream settings. More graph edges or computation alone do not establish better compression. |
| [Neuron permutation](../benchmarks/weights/20261017-linux-packages-gcc13-v1) | Both platform fixture archives stay identical; measured release components shrink 8,563 bytes. A [real full-input prefix check](../benchmarks/weights/20261018-release-prefix-v2) matches 4 MiB of coder output and the compressed dictionary, extending over 2 MiB beyond the main-text marker. | Complete the archive and decoder/resource verification. Prefix identity alone is far short of the next 1% improvement. |
| [Exact link target](../benchmarks/model-variants/20261017-retrieval-linux-screen-v1) | Mac fixture payloads improve by 5 and 2 bytes; native Linux saves 3 bytes on the screen but loses 5 on the disjoint fixture. All restore exactly. | Reject under this protocol; third-range Mac loses 5 bytes and Linux saves 2. All six outcomes are retained without retuning. |
| [Structured pruning](../benchmarks/weights/20261017-pruning-screen-summary-v1) | All six round trips pass, but 5%, 10% and 25% removals add roughly 16–17 KB, 30–31 KB and 54–55 KB per fixture, about 49–76 times their gross model-saving budgets. | Reject all three unretrained candidates; do not spend Linux or reserved-range runs on them. |
| [Alias prediction refresh](../benchmarks/model-variants/20261017-alias-screen-v1) | Exact restoration and unchanged context counts; Mac screen adds 4 bytes and disjoint ties. | Fails both-fixture improvement gate; keep the original callback. |

Priorities:

1. Finish the active paired experiments and preserve every outcome. The
   [real release prefix protocol](../benchmarks/weights/20261017-release-prefix-protocol-v1)
   initially matched the first 1 MiB emitted after full enwik9 preprocessing,
   but stopped in metadata with the transformer disabled. The
   [longer protocol](../benchmarks/weights/20261017-release-prefix-protocol-v2)
   requires main-text coverage before accepting a 4 MiB prefix. It remains a
   bounded invariance check, not a complete archive, round trip or score.
2. Move only surviving hypotheses to larger probes. The exact-target candidate
   activated the [reserved confirmation range](../benchmarks/model-variants/20261017-retrieval-confirmation-protocol-v1)
   before Linux exposed its disjoint regression:
   150 complete pages, 1,000,794 raw bytes. Do not reuse its score for tuning
   while calling it untouched validation. The upstream model already trained
   on the target corpus; this separation protects our experiment decisions.
3. Run the exact baseline and eventual candidate to completion on persistent
   native Linux x86-64 hardware, with isolated SFX restoration and time, memory
   and scratch-disk measurements. A standard hosted CI job cannot finish the
   upstream-reported roughly 49-hour encoder and another 49-hour decoder.
4. Seek a material improvement in prediction or the model-size/payload tradeoff.
   The [weight audit](../benchmarks/weights/20261017-container-audit-v1) finds only
   about 2.2 KB between current int4 coding cost and independent per-tensor
   empirical entropy. This limits simple frequency-table tuning, not more
   expressive models of correlations. The first unretrained pruning choices
   fail by a large margin. The
   [full training-row dump](../benchmarks/training/20261017-native-dump-v1) now
   matches its published 7.1 GB hash. The diagnostic read cache reproduces all
   four original output hashes, with observed 13.5 versus 40 minute concurrent
   run times and about 509 MB extra resident memory; this is not a controlled
   production speed result. MLP instrumentation preserves both archives: all
   12,218 neurons activate, and the old 5% removals can include about 17% of a
   layer's squared activation mass. A separate activation-aware, compensated
   or retrained-model experiment would still need new measured archives.

5. Investigate the [small final bit predictor](website/docs/research/bit-predictor.md)
   as a CPU training route. Upstream trained its 7,386-byte model on only the
   first 20% of model bits. The original large trace is absent, but the new
   bounded writer and public replay verifier match every live integer
   probability on both Mac and native Linux fixtures with the compressor's
   deterministic math. The earlier Linux system-math mismatch is retained.
   A one-pass screen-selected BF16 update saves [148 bytes on the screen](../benchmarks/training/20261017-bitl-archive-screen-v1)
   and [91 bytes on the disjoint fixture](../benchmarks/training/20261017-bitl-archive-holdout-v1)
   in actual Mac archives; both restore exact original XML and retain matching
   context counts. Native Linux saves [136 bytes on the screen](../benchmarks/training/20261018-bit-weight-linux-screen-v1)
   and [93 on the disjoint fixture](../benchmarks/training/20261018-bit-weight-linux-holdout-v1),
   both with exact restoration and matching context counters. The [Linux release package](../benchmarks/training/20261018-bit-release-v1)
   reproduces the published baseline and saves 16 bytes in the compressor and
   16 bytes in the independent decoder prefix, a 32-byte component reduction.
   A fixed-weight [third Mac range](../benchmarks/training/20261018-bit-weight-third-range-v1)
   also saves 95 payload bytes and restores exact original XML; it was previously
   used for an unrelated retrieval experiment, so is supporting rather than
   untouched validation.
   A separate 4 MB [native Linux comparison](../benchmarks/training/20261018-bit-weight-linux-broad-v1)
   saves 250 payload bytes (476,220 → 475,970 B), with exact restoration and
   matching contexts. This is a stronger length check for the fixed model;
   after the same range is used for broader training, its score cannot be
   treated as that new model's holdout.
   Measure longer streams and the complete prize archive. These reused fixtures are not a
   full-corpus or prize score. A separate frozen [extra-pass trial](../benchmarks/training/20261017-bitl-multi-pass-v1)
   lowers screen probability cost by another 282.3 bytes at 16 passes but
   worsens disjoint cost by 90.6 bytes against the one-pass model. Reject that
   checkpoint and expand training coverage rather than fitting this trace
   longer. A [separate 4,002,523-byte range](../benchmarks/training/20261018-broad-trace-protocol-v1)
   at enwik8 offset 20,013,121 is now prepared with exact source restoration;
   [baseline/trace archive checks](../benchmarks/training/20261021-broad-trace-v1)
   now pass: identical 476,220-byte archives, exact original XML restoration
   and matching encoder/decoder records for 9,746,875 model bits. The
   [frozen replay](../benchmarks/training/20261021-broad-replay-v1) matches
   every live integer probability and rejects a wrong-first control. A
   [one-pass CPU training protocol](../benchmarks/training/20261021-broad-train-protocol-v1/protocol.json)
   was frozen before training from it. The [result](../benchmarks/training/20261021-broad-train-v1)
   fails the screen gate: the best broad-trained BF16 model is 22.9
   probability-cost bytes worse than the prior screen-trained checkpoint.
   No holdout or archive trial followed. This suggests testing transfer or
   a complementary update, not longer fitting of this range by default.
   A frozen [25% weight blend](../benchmarks/training/20261022-bitl-blend-v1)
   of prior and broad checkpoints passes both replay-cost gates (−8.6 B
   screen, −31.3 B disjoint versus prior). Its [real archive trial](../benchmarks/training/20261022-bitl-blend-archive-protocol-v1/protocol.json)
   passes: versus prior it saves [9/32 bytes on Mac](../benchmarks/training/20261023-bit-blend-mac-screen-v1)
   and [11/30 bytes on Linux](../benchmarks/training/20261023-bit-blend-linux-screen-v1)
   across screen/disjoint, with exact restoration and matching contexts.
   The [native Linux packed release](../benchmarks/training/20261025-bit-blend-release-v1)
   reproduces both pinned baseline and prior packages and saves another
   37 measured component bytes versus prior (17 compressor + 20 decoder
   prefix). It is a small confirmed component gain; full enwik9 remains open.

Continue signing and pushing immutable reports, protocols, hashes and failures
to `main`; keep the [educational research pages](https://bbondy.github.io/hutter/research/experiment-playbook)
in sync. The full prize score, resource eligibility and eventual submission
license/attribution review are still outstanding. No measured result here yet
establishes a winning entry.

## Recommendation

Keep the Rust code as a small experiment lab. Make reproducing and improving a
recent competitive compressor the main prize effort. The current codecs are
useful baselines, but extending this collection without a stronger reference is
unlikely to catch the frontier. No result here establishes prize competitiveness.

First fix measurement and wasted work, then run isolated experiments. Do not
start with a rewrite, an enormous model, or a sweep of every constant.

## Target and accounting

The [official page](https://hutter1.net/prize/index.htm), checked October 17,
lists fx2-cmix-T at **100,424,672 total bytes** and the next target below
**99,420,425 bytes**. The README previously used the 2024 record.

[cmix-neif 1.0](https://github.com/marwoelk/cmix-neif-1.0) reports **95,914,051
total bytes**, with acceptance pending in the
[Large Text Compression Benchmark](https://mattmahoney.net/dc/text.html).
If accepted at that score, its mathematical 1% threshold is at most 94,954,910
integer bytes. Plan for **under 94 MB total**, with margin; this is an engineering
target, not a prediction that this will win. Recheck the submission queue.
LTCB's headline ranking omits the compressor cost used in the prize: its numbers
are not interchangeable with prize totals.

The [detailed rules](https://hutter1.net/prize/hrules.htm) score compressor plus
SFX archive, or compressor + twice decoder + payload for the separate-decoder
alternative. The latter reduces to **2 × executable + payload** when the same
executable serves both roles. Required options count too; permitted zipped
representations affect final accounting. We corrected `stats`, which previously
counted only one copy of this repo's shared executable. It now labels the number
as a development estimate, not a validated submission score.

Each executable must fit the machine-normalized time budget `70,000/T` hours,
10 GB RAM and 100 GB temporary disk, with no GPU at runtime. Target Linux x86-64
for verification. Leave headroom, including input/output buffers and models.

## Sample decision: add real slices, retain the tiny smoke test

`data/sample.txt` is 179 bytes in two English sentences. It has none of the scale
needed to measure Wikipedia context learning, XML/wiki syntax, metadata, repeated
articles or memory growth. Repeating those sentences would create misleadingly
easy artificial data. Keep the file for fast roundtrips, not model selection.

`scripts/make_samples.py` checks official size and SHA-1, preserves raw bytes,
and writes a manifest with SHA-256 and exact offsets. No XML parsing, whitespace
normalization, random byte sampling or concatenated artificial boundaries.

| Tier | Source interval, in decimal bytes | Use |
|---|---|---|
| Smoke | Existing 179-byte file | Wiring only; add edge fixtures when modifying codecs |
| Screen | `[0, 100000)` | All codecs; reject obvious failures, not close contenders |
| Development | `[0, 1000000)`, `[49000000, 50000000)` | Fast comparison on two different contiguous regions |
| Confirmation | `[89000000, 90000000)` | Freeze a candidate before checking this slice |
| Promotion | `[0, 10000000)` | Model warm-up and resource scaling |
| Reference | Official enwik8, 100 MB | External comparability and longer-context behavior |
| Prize | Official enwik9, 1 GB | Only basis for a prize claim |

Once enwik9 is downloaded, the generator adds 1 MB regions at each 100 MB offset
from 100 MB through 900 MB. They expose regions absent from enwik8. Do not call
the enwik8-only suite representative of the whole gigabyte.

Cold slices discard earlier learned state and long-range matches. Preserve order
and compare identical streams. For mature models, add checkpointed warm-prefix
experiments and per-region coding loss, but always verify the final full stream.
Sample size and full-corpus size improvements can disagree. Held-back slices
protect research decisions; the contest itself permits corpus-specific tuning.

## Findings in the current models

| Family | Assessment | Next action |
|---|---|---|
| Huffman / naive LZ77 | Useful simple references; the LZ77 window is 4 KiB | Freeze as controls; do not spend prize research here |
| Byte `ppm-o1`…`ppm-o6` | Simple escape/backoff; no exclusion in this implementation | Retain order-four reference; higher order is not automatically better |
| `ppmd` | Exclusion-based order-six PPM-style model; currently useful ratio/speed reference | Use for fast Rust experiments; it is not equivalent to mature upstream PPMd |
| `ppmd-bit` | Codes a byte-context PPM distribution bitwise | Small measured size gain over `ppmd`, substantial time cost |
| Raw bit PPM | Orders count bits, not bytes; high orders grow huge tables and perform poorly here | Stop broad high-order sweeps; diagnose smoothing and memory first |
| `ppm-byte-mix` | Copies predictions and builds a score HashMap each byte; weight update differs from final coded loss | Fix probability objective before optimizing its allocation overhead |
| `ppm-mix` / `ppmd-mix` | Many correlated logits with large positive initial weights | Measure saturation and overconfidence; compare conservative initialization and calibration |
| `ppm-match-mix` | Disabled bit predictor still updates its full state; match evidence limited to four bytes | Highest-priority local iteration fix, followed by a match-model experiment |
| `wikimix5` | Implemented heuristic coder, not the documented skeleton; fixed weights and top-k truncation | Requires calibrated probabilities/escapes, not more hand-picked candidate bonuses |

Specific code evidence:

- `HybridModel::observe_bit` in `src/ppm_match_mix.rs` ignores the expert enable
  flags when updating state. The current byte+match configuration still populates
  64 bit-context maps. `profile` therefore cannot measure true expert-removal
  savings; two of its rows also use the identical configuration.
- `refresh_candidates` passes `current = data.len() - 4` into `match_length`,
  whose loop requires `current + length < data.len()`. Thus the nominal 64-byte
  lookahead cannot see more than four bytes. Use evidence from already-decoded
  history or maintained active matches, never future plaintext.
- Most context maps have no capacity limit. Count rescaling does not free
  contexts. Match windows do not bound the retained `data` vectors or key sets.
  Entire input, output or payload buffers introduce further memory costs.
- WikiMix keeps only two/three top symbols from some experts, then twelve from
  the fixed-weight sum. Its constant escape weight competes against increasing
  raw counts; a miss then costs a uniform byte. This can explain expansion,
  but individual ablations are needed to quantify each cause.
- Model families duplicate arithmetic coding and history logic across thousands
  of lines. Consolidate only after capturing golden archives and establishing
  improvement; a large cleanup is not the first compression experiment.
- Floating-point `ln`/`exp` and quantized probabilities need cross-machine
  determinism checks. A local roundtrip alone does not prove Intel/AMD portability.

## Initial experiment sequence and stop conditions

1. **Establish the reference and trustworthy measurements.**
   [Issue #1](https://github.com/bbondy/hutter/issues/1): pin and reproduce
   fx2-cmix-transformer on Linux x86-64; then assess cmix-neif. Keep licensed
   upstream checkouts separate from the MIT lab and preserve attribution.
   Generic sample support may require a different frontend from the submitted
   enwik9-specialized executable; record that distinction. Reuse public weights
   before allocating training compute.
2. **Remove wasted work, then bound memory.**
   [Issue #7](https://github.com/bbondy/hutter/issues/7): disabled experts must not
   update state. Expect a resource win with identical PMM3 archives; this alone
   cannot improve ratio. [Issue #2](https://github.com/bbondy/hutter/issues/2):
   deterministic table capacities/eviction, compact allocation and bounded
   history. Measure 100 KB → 1 MB → 10 MB → 100 MB before trying 1 GB.
3. **Make the existing predictors useful.**
   [Issue #3](https://github.com/bbondy/hutter/issues/3): repair long-match evidence
   and test window sizes. [Issue #4](https://github.com/bbondy/hutter/issues/4):
   compare expert-only, fixed linear mixture, conservative logistic mixture,
   context-dependent mixing and probability calibration. Track actual coded
   loss, including escapes and quantization. Reject added experts that have no
   net contribution within the full mixture.
4. **Improve Wikipedia representation against a strong backend.**
   [Issue #5](https://github.com/bbondy/hutter/issues/5): metadata/prose separation
   and integer deltas; dictionary/case/entity transforms; article ordering with
   inverse permutation costs. Existing winners already do substantial
   preprocessing: compare incremental improvements, not toy-codec-only gains.
   Every transform must restore exact bytes, including the truncated last record.
5. **Experiment with compact neural corrections.**
   [Issue #6](https://github.com/bbondy/hutter/issues/6): start with a small residual
   corrector or quantized byte model. The accepted
   [transformer writeup](https://github.com/astOwOlfo/fx2-cmix-transformer-v1/blob/main/writeup.md)
   demonstrates offline GPU training plus shipped compact weights and CPU
   inference. Training on enwik9 is not inherently disallowed; omitting the
   resulting knowledge from the scored package is the accounting trap. Count
   weights wherever stored, often twice, and measure the final mixture's benefit.

For each experiment record a hypothesis, baseline revision, one change, exact
configuration and expected cost. Run both development slices, then confirmation,
10 MB, enwik8 and finally enwik9 for promising survivors. This funnel is a default,
not a proof: models that require long warm-up deserve a deliberate longer probe.
Repeat timing trials at least three times before choosing between close results;
archive bytes should be deterministic. Re-measure combinations: benefits overlap.

`8 * archive_bytes / input_bytes` is the development bits-per-byte metric.
On enwik9, 0.01 bits/byte represents 1.25 MB of payload; subtract all added
code/weight/metadata bytes before calling it a win. Smaller archives that exceed
resource constraints do not advance the prize objective.

## Things likely to waste time

- Ranking on the tiny file or a single short prefix; extrapolating a percentage
  gain to enwik9 without measuring warm-up, eviction and long-distance effects.
- Adding all available experts, raising every order/window, or treating larger
  context counts as automatically better. Current measured mixtures refute that.
- Optimizing Huffman/naive LZ77 into the prize strategy, or porting an entire
  winning C++ compressor to Rust before testing a new idea.
- Using a huge pretrained LLM while ignoring serialized model cost or assuming
  GPU inference is allowed. Compact neural models remain a valid research path.
- Lossy XML cleanup, article reordering without inverse information, or a
  dictionary available only on the encoder's machine.
- Confusing a short-input likelihood gain, an LTCB result, or the CLI's native
  executable estimate with a compliant prize score.
- Assuming a pending submission is accepted, or that today's 1% threshold will
  survive the experiment cycle. Submission order matters.

## What this setup provides

`make samples` and `make bench-suite` now provide reproducible inputs and serial
round-trip measurements. The runner stores commands, input/archive/binary hashes,
revision/status, platform, time and peak RSS for both phases. Repeats check archive
identity. Failures/timeouts remain in JSONL and cause a nonzero exit. Output
directories cannot be reused accidentally. Restored duplicates are deleted only
after size and SHA-256 verification; archives and logs remain.

Initial Rust-runner limitations: no hard RSS enforcement, no Linux reference-machine run, no temporary
disk peak measurement, no model-loss traces, and no full enwik8/enwik9 compression
yet. Small timings include process startup and timer/polling overhead. Record a
clean commit and fixed build flags for subsequent publishable experiments.

See [the initial benchmark report](benchmarks/2026-10-17/README.md) for measurements.
