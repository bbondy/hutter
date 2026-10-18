# Cycle-inspired article ordering: experiment protocol

The 100 prisoners strategy exploits cycles in a permutation. It does not itself
reduce the information needed to encode that permutation. The compression
hypothesis here is narrower: reorder Wikipedia articles so more of the pages
linking to an article have already been decoded when that article begins. The
existing cmix-neif link-context model can then potentially use those earlier
mentions. Wikipedia's graph has multiple links per page, so it is not the
prisoners' permutation.

Upstream already uses an embedding-derived article order, encoded as a rule and
residual, with redirects first and special page classes grouped. Its README
section 4.3 says that orders designed for more incoming-link context were not
tested and may need matching transformer retraining. This experiment changes
only fixture order; it retains the existing model weights.

## Fixed protocol, before compression results

- Screen: existing first 1 MB complete-page fixture, enwik8 byte interval
  `[1404, 1035001)`: 1,033,597 bytes, 172 pages.
- Disjoint follow-up: first complete page at/after offset 49,000,000, through the
  first complete end after 1 MB: `[49000139, 50006116)`, 1,005,977 bytes, 138 pages.
  Selection, graph algorithm and random seed are fixed before reading scores.
  Disjointness concerns experiment selection, not data unseen by the inherited
  pretrained weights.
- Three orders of exactly the same pages: source order, graph order, and a random
  control (sort SHA-256 of `20261017:PAGE_ID`). No page text changes.
- Graph: exact-title wiki-link pairs after XML unescaping; remove fragments and
  pipe display text, without case/underscore normalization or redirect resolution.
  Deduplicate repeated source/target pairs and exclude self-links. This is a
  proxy; cmix token matching, prefix behavior and prompt budgets differ.
- Graph order: topologically order strongly connected components; choose the
  earliest source-position component when several are available. Within a cycle,
  choose maximum remaining outdegree minus indegree, breaking ties by source
  position. This heuristic cannot make every cycle edge point forward and is
  not claimed to find an optimum. Large strongly connected components will need
  a more scalable algorithm before applying this implementation to enwik9.
- Preprocess each variant with the same verified phda9 helper. Invert and sort
  recovered pages by their unique page IDs. Reject inputs whose source order is
  not already strictly increasing by ID. Verify the exact original bytes.
- Benchmark with one frozen native binary, dictionary and weights, with a fresh
  process per variant. Decode every archive, invert preprocessing and restore
  original order before accepting a result. Preserve successful and failed runs.
- Compare payload bytes, plus explicit order metadata (zero for these fixtures:
  the decoder sorts IDs already present in the recovered text). Added decoder
  and encoder code still needs packaging and accounting in a submission. Assets
  and executable are excluded from these fixture payload numbers.
- Timing is exploratory, especially for concurrent processes. One deterministic
  size trial per order does not estimate variation across corpora or random seeds.

## Why the larger sample is necessary

The previous 19-page, 117,161-byte fixture has **zero internal exact-title links**.
The 172-page fixture has 66. Source order makes 42 of them available before their
target; graph order makes 54 available; the random control makes 35 available.
Only 24, 26 and 21 pages respectively have at least one such earlier incoming
link. More edges do not guarantee more useful tokens or fewer compressed bytes.

The disjoint fixture has 63 edges, of which 31/38/31 are forward in
source/graph/random order. Graph ordering displaces 123 of its 138 pages, compared
with 45 of 172 in the screen. That disruption can lose locality in other models.

The [saved graph audit](../../../benchmarks/article-order/20261017-graph-audit-v2/screen.json)
finds 11 reciprocal link pairs in the screen. Each forces one backward edge,
so no order can exceed 55 forward links; the heuristic reaches 54. This is an
upper bound, not a proof that 55 is attainable. A near-maximal proxy can still
fail to improve compression.

An [audit of all complete enwik8 pages](../../../benchmarks/article-order/20261017-graph-audit-v2/enwik8.json)
covers 12,346 pages and 62,552 internal exact-title edges. Its largest strongly
connected component contains **5,726 pages**. The prisoners' picture of disjoint
simple loops does not transfer directly: a large mutually reachable region
still needs an internal ordering. The audit only decomposes the graph; it does
not run the expensive greedy ordering or compress this larger set. Both frozen
fixture orders and graph metrics remained unchanged when the SCC audit was
factored out and support for empty self-closing text elements was added.

## Interpretation gates

This is a **source-order fixture screen**, not a comparison against upstream's
competitive embedding/residual order. A smaller graph payload would justify the
next experiment, not a claim of beating upstream or winning the prize.

1. Require exact original-byte reconstruction and include all ordering costs.
2. Repeat the frozen method on the disjoint fixture; do not tune on its result
   and keep calling it held out.
3. Compare against upstream's actual order on the full pipeline, ideally with
   local swaps that preserve topical clusters and redirect/calendar rules.
4. Measure actual supplied context tokens, not just this graph proxy; separate
   context benefits from generic model-locality effects.
5. Confirm candidate ranking on Linux x86. Native and Linux fixture sizes already
   differ slightly, sometimes in opposite directions.
6. Only then consider matched retraining, full enwik9 runs and total submission
   package size/runtime/RSS. Tiny or disjoint fixtures cannot establish prize gains.

## Reproduce

```sh
python3 scripts/article_order.py prepare \
  --enwik8 data/enwik8 --build build/native-parity-v1 \
  --output build/order-screen-v1 --phase-mode legacy
python3 scripts/article_order.py prepare \
  --enwik8 data/enwik8 --build build/native-parity-v1 \
  --output build/order-holdout-v1 --phase-mode legacy --start-offset 49000000 --role holdout
python3 scripts/native_cmix.py bench \
  build/order-screen-v1/source.ready \
  --build build/native-parity-v1 --manifest build/order-screen-v1/manifest.json \
  --output build/order-screen-source-v1 --timeout 3600 \
  --record 20261017-order-screen-source-v1 \
  --note 'Predeclared article-order screen: source order; payload only'
```

Repeat the benchmark command for `graph` and `random`, using unique output and
history IDs. The sample manifests retain page hashes, exact permutations,
graph statistics, helper and preparation-source hashes. The runner retains
binary, dictionary and weight hashes alongside each result.

`scripts/order_history.py summarize` is the comparison gate for this experiment.
Unlike the ordinary benchmark history command, it permits different prepared
hashes only when the declared variants restore the same original bytes and
article set. It verifies the saved archive, decoder output, model/asset hashes,
article count and helper, then retains the logs, manifest and result hashes.

```sh
python3 scripts/order_history.py summarize \
  --manifest build/order-screen-v1/manifest.json --build build/native-parity-v1 \
  --runs build/order-screen-source-v1 build/order-screen-graph-v1 build/order-screen-random-v1 \
  --output benchmarks/article-order/20261017-screen-v1
python3 scripts/order_history.py list
```

## Cheap codec controls

The saved `20261017-standard-v1` controls use Python zlib level 9, bzip2 level 9
and XZ preset 9 on the same prepared streams. All 18 decoder checks restored the
prepared bytes. These codecs do not have cmix's link-context model.

| Fixture | Codec | Source bytes | Graph bytes | Random bytes | Graph delta |
| --- | --- | ---: | ---: | ---: | ---: |
| First 1 MB | zlib-9 | 355,673 | 355,102 | 358,646 | −571 |
| First 1 MB | bzip2-9 | 284,665 | 287,207 | 287,106 | +2,542 |
| First 1 MB | xz-9 | 294,760 | 294,624 | 295,660 | −136 |
| Disjoint 1 MB | zlib-9 | 350,839 | 349,965 | 357,132 | −874 |
| Disjoint 1 MB | bzip2-9 | 283,732 | 283,888 | 284,772 | +156 |
| Disjoint 1 MB | xz-9 | 289,676 | 289,712 | 291,216 | +36 |

This establishes that graph order is not uniformly better across codecs. Even
XZ's small direction changes between fixtures. These controls cannot predict
cmix's result or establish that an improvement comes from link context.

## Pipeline limitation found while the screen ran

The development binaries parameterize metadata article count but retain the
full-corpus redirect-block cutoff of **71,148 pages**. See
`src/redirect_table.h:redirect_block` and
`src/tf1/tf1_prompt.h:CoderPrompt::ImRedirectBlock` in the pinned engine.
`page_form.h` uses the former to escape non-redirect text inside that block;
the prompt code uses the latter to insert a four-token `#rd` prompt before each
page. Thus ordinary fixture pages receive that redirect-block marker too. The running
fixtures all log entry into the redirect block and never reach main text.

This does not by itself break reversibility or turn off all link processing.
It does mean that these scores describe the inherited small-fixture pipeline,
not a representative main-text phase of the full submission. Retain the first
screen for evidence, but correct fixture phase boundaries and measure actual
supplied context before expensive full-corpus or retraining work. Do not silently
replace the existing binary and compare the resulting size change as an ordering
gain. Earlier parity round-trip findings remain valid for their saved binaries.
The correction and telemetry acceptance checks are tracked in
[issue #13](https://github.com/bbondy/hutter/issues/13).

## Native screen

All three native decoders restored their prepared inputs exactly. Inverse phda9
and page-ID sorting then restored the same **1,033,597 original bytes** for every
variant. The [verified comparison](../../../benchmarks/article-order/20261017-screen-v1/report.json)
retains the checks, archive/input/build/asset hashes, manifest and process logs.
Each variant has one trial; repeat determinism was not independently tested here.

| Order | Payload bytes | Delta from source | Forward links |
| --- | ---: | ---: | ---: |
| Source | 120,337 | 0 | 42 |
| Graph | 120,359 | +22 (+0.018%) | 54 |
| Random | 120,936 | +599 (+0.498%) | 35 |

This particular heuristic has no measured payload advantage on the first
fixture. It is much closer to source order than the random control, but that
does not isolate a link-context effect: model locality, metadata coding and
the inherited redirect-block prompts also change the result.

The disjoint fixture remains preselected and prepared; its standard-codec
controls are saved. After discovering the phase-boundary limitation, we defer
its expensive cmix comparison until a corrected baseline exists. Likewise,
there is no promising current graph gain to send to Linux confirmation.

## Next moves and iteration cost

1. Fix phase configuration and add actual context telemetry under issue #13.
   Include a small correctness fixture with a real incoming-link example and
   both redirect and main-text pages. This deliberately structured fixture
   exercises behavior; it is not a ranking benchmark.
2. Freeze a new three-order baseline after that correction. Use the same
   contiguous first and disjoint article sets and retain the negative v1 result.
3. Compare upstream's actual competitive order with small graph-guided changes
   inside its topical groups, preserving redirect and calendar handling. Our
   full SCC ordering can disrupt locality and cannot be applied naively to a
   large cyclic component.
4. Only pursue matching transformer retraining or full-corpus Linux runs after
   that experiment produces a gain worth the code/side-data and resource costs.

The three native encoders ran concurrently and each took about 616 seconds,
including about 153 seconds of dictionary pretraining. These are exploratory
wall times, not prize hardware measurements. Keep exact-hash baseline results
so new order candidates do not require recomputing the unchanged baseline.
Use graph auditing and cheap codecs to reject broken setups, not to predict a
cmix winner. Smaller fixtures retain the expensive dictionary startup and can
remove the very cross-article structure being tested.
Decoding took 612 seconds per variant, with about 150 seconds of dictionary
pretraining. Peak reported resident memory was approximately 6.0 GB per process.
No Linux ranking confirmation or full-submission package result is claimed.

## Runtime-only phase attempt (v2, rejected)

The [v2 protocol](../../../benchmarks/article-order/20261017-protocol-v2/protocol.json)
retains both original raw page sets. Redirects move into one fixed prefix using
upstream's literal classifier; only the remaining ordinary pages are permuted.
The screen has 127 redirects and 45 ordinary articles; the disjoint fixture has
28 redirects and 110 ordinary articles. Source/graph/random forward-link counts
are now 42/54/44 and 34/38/34 respectively. These are new baselines.

The shared development patch parameterizes both redirect-cutoff consumers.
`--native-corpus N R` is required on both sides, with an explicit 16-byte header
that stores N and R and is included in payload sizes. The full-corpus defaults
and old `--native-pages` behavior remain available. Header mismatch checks run
before pretraining. The exact pinned upstream source is unchanged.

Read-only JSON reports expose actual transformer link-prefix tokens fed, prompt
counts and alias-channel activity. Accepted comparisons require matching encoder
and decoder counters, the declared redirect prompt count and main-text entry.
Six native round trips and a telemetry-disabled repeat of screen source completed
under this protocol. They are retained below as rejected diagnostic evidence;
the shared Linux build was also corrected for its include search paths.

## Preparation and runtime configuration (v3)

Telemetry exposed two issues in v2. First, upstream emits redirect prompts after
page separators, so the first page has no leading redirect prompt. The expected
count is `max(R - 1, 0)`, not R. Second, the standalone phda9 helper includes
`page_form.h` and performs redirect coding itself. Configuring only the runtime
left the helper's full-corpus cutoff active: ordinary articles retained escapes.
The v2 trials are diagnostic evidence, not accepted corrected baselines.

The [v3 protocol](../../../benchmarks/article-order/20261017-protocol-v3/protocol.json)
requires identical `--native-corpus N R` arguments in preparation, encoding,
decoding and inverse preparation. Manifests save helper arguments, and the
comparison gate rejects a missing or different helper configuration. New tests
exercise zero, mixed and all-redirect prefixes with exact raw restoration and
reject a wrong declared page count. The frozen raw pages and all three orders
are unchanged. Prepared streams shed exactly 45 escape bytes on the screen and
109 on the disjoint fixture; one ordinary body in the latter needed no escape.
This is a protocol correction, not an ordering gain.

## Accepted v3 results

The [screen](../../../benchmarks/article-order/20261017-screen-v3/report.json) and
[disjoint comparison](../../../benchmarks/article-order/20261017-holdout-v3/report.json)
pass prepared-stream decoding, inverse preparation and original-byte restoration
for all six trials. Both sides report identical context counters, the expected
126/27 redirect prompts and main-text entry.

| Order | Screen payload | Delta | Disjoint payload | Delta |
| --- | ---: | ---: | ---: | ---: |
| Source | 119,969 | — | 118,411 | — |
| Graph | 119,975 | +6 | 118,433 | +22 |
| Random | 120,083 | +114 | 118,646 | +235 |

Graph order feeds **2,897 vs 2,319** actual link-prefix tokens on the screen and
**1,531 vs 1,359** on the disjoint set. Pages receiving prefixes rise from 24 to
26 and 33 to 35. More supplied context therefore did not improve either payload.
This comparison changes order and several model contexts together; it does not
isolate the value of the link channel itself.

The [telemetry-disabled repeat](../../../benchmarks/article-order/20261017-screen-v3/telemetry-invariance.json)
produces the identical 119,969-byte archive. Encoding took 659–669 seconds and
decoding 763–776 seconds with other jobs active; these are exploratory timings.
All payloads include the same 16-byte development frame and exclude executables,
dictionary and weights. No candidate from this source-order batch is promoted.
The projected upstream-order comparison remains a separate, predeclared test.

## Full upstream order reconstructed natively

The new `prepare_order.cpp` driver calls the pinned census transform, fixed
intro/main/coda split, comment-index transform and article reorder on verified
enwik9. On this Mac it reproduces the upstream acceptance digest for the entire
998,030,918-byte reordered main stream:
`28ca879dcfdafe7833b042f58cfee517` (MD5), with independently saved SHA-256
`b30426195038b77c57dd207db613232c1058523176399f7b4800647f6ed28d7e`.
The [saved validation](../../../benchmarks/article-order/20261017-upstream-order/validation.json)
contains input, source, compiler, residual, executable and page-index provenance.
The run took 94 seconds and indexed all 243,425 unique page IDs. This validates
these preprocessing/order stages; it is not a full compression result.

The front block contains **71,110 redirects plus 38 excluded ordinary pages**.
Its physical length is 71,148. The order also preserves 3,417 calendar pages and
five special article classes. A faithful projected-order experiment must preserve
these groups, including excluded pages, instead of assuming the front block is
purely redirects. The next comparison will project the exact upstream order
onto the frozen raw article sets, then test limited graph-guided changes.

The [v2 rejection record](../../../benchmarks/article-order/20261017-rejected-v2/rejection.json)
retains all six exact raw round trips, the failed original counter checks and the
helper-configuration issue. Its telemetry-disabled repeat produced an identical
archive. The corrected v3 Mac/Linux builds also pass the saved
[initialization check](../../../benchmarks/parity/20261017-fixture-v3-init/report.json).
The native and Linux binaries are respectively byte-identical to their preceding
v2 builds; the v3 preparation helper and input streams changed. Initialization
agreement still does not prove cross-decoding or Linux candidate ranking.

## Projected competitive-order comparison, predeclared

The [projection protocol](../../../benchmarks/article-order/20261017-projection-protocol-v1/protocol.json)
compares exact upstream order with two candidates on the same raw pages and the
same v3 binary/assets. All special-page positions and full-order class-region
boundaries stay fixed. The local candidate makes only strictly improving adjacent
link swaps, with four passes and a 4,096-full-rank displacement bound. The graph
candidate runs the existing SCC heuristic separately within each ordinary region.
The baseline supplies tie order. No scores from these variants have been read.

The local proposal moves four screen pages (forward links 45 to 47) and two
follow-up pages (33 to 34). The broader graph proposal moves 27 and 42 pages
(45 to 54, and 33 to 35). Their measured sizes and actual context use will decide
whether any is worth continuing. A third range starting at enwik8 byte 80,000,000
is reserved in advance for confirmation if a candidate wins both existing sets;
the repeatedly examined disjoint set is not an untouched validation set.

## Projected-order v1 outcome and subsequent portability correction

The [screen](../../../benchmarks/article-order/20261017-projected-screen-v1/report.json)
and [disjoint result](../../../benchmarks/article-order/20261017-projected-holdout-v1/report.json)
restore the original bytes for all six orders:

| Order | Screen payload | Delta | Disjoint payload | Delta |
| --- | ---: | ---: | ---: | ---: |
| Upstream projection | 119,868 | — | 118,442 | — |
| Local swaps | 119,884 | +16 | 118,438 | −4 |
| Graph within regions | 119,896 | +28 | 118,456 | +14 |

Actual prefix tokens are 1,893 / 2,183 / 2,733 on the screen and
1,361 / 1,417 / 1,417 on the follow-up. Neither candidate improves both sets;
the reserved third range remains untouched.

A later full-stream check found an independent entity-preprocessing portability
defect. All v1–v3 Mac fixture results above use that older entity representation.
They remain valid native round trips, but are not canonical Linux-input results.
The Linux training tool matched both full upstream stream hashes. Defining two
inherited signed-overflow operations as unsigned then made the Mac tool match
those hashes too. See the [pipeline records](../../../benchmarks/pipeline/README.md).

Projection protocol v2 regenerates the prepared bytes after this fix, retaining
identical raw pages, permutations, local-swap parameters and model weights. It
establishes new baselines; any size change from the representation correction is
not an ordering improvement. The fixed-input model tests have the same reset.

## Canonical projection and context outcomes

After the unsigned entity fix, all six canonical order trials restore the exact
original XML and pass encoder/decoder context checks:

| Order | Screen payload | Delta | Disjoint payload | Delta |
| --- | ---: | ---: | ---: | ---: |
| Upstream projection | 119,065 | — | 117,438 | — |
| Local swaps | 119,073 | +8 | 117,427 | −11 |
| Graph within regions | 119,096 | +31 | 117,476 | +38 |

The [screen](../../../benchmarks/article-order/20261017-projected-screen-v2/report.json)
and [disjoint](../../../benchmarks/article-order/20261017-projected-holdout-v2/report.json)
records use protocol v2. Neither candidate improves both, so neither advances.
The reserved range at byte 80,000,000 remains untouched.

The fixed-input link-context changes also fail promotion:

| Model | Mac screen | Mac disjoint | Linux screen | Linux disjoint |
| --- | ---: | ---: | ---: | ---: |
| Upstream | 119,065 | 117,438 | 119,067 | 117,426 |
| Budget 128 | 119,077 (+12) | 117,448 (+10) | 119,070 (+3) | 117,436 (+10) |
| Chunk 32 | 119,077 (+12) | 117,442 (+4) | 119,076 (+9) | 117,433 (+7) |
| Prefix disabled | 119,084 (+19) | 117,454 (+16) | 119,086 (+19) | 117,456 (+30) |

All sixteen pairs restore original XML, with identical context counters and zero
prefix tokens for the disabled control. The canonical prepared bytes match across
platforms. Source/asset/compiler checks permit only each declared model change.
The [native records](../../../benchmarks/model-variants/20261017-screen-v2/report.json)
and [native disjoint](../../../benchmarks/model-variants/20261017-holdout-v2/report.json)
preserve concurrent exploratory timings. The
[Linux screen](../../../benchmarks/model-variants/20261017-linux-screen-v2/report.json)
and [Linux disjoint](../../../benchmarks/model-variants/20261017-linux-holdout-v2/report.json)
come from [workflow 39080868994](https://github.com/bbondy/hutter/actions/runs/39080868994),
which ran each host's models serially. Downloaded binaries, archives, decoded
streams, metadata and logs match their recorded hashes; an independent Mac
inverse helper also restored all original raw bytes. Supplemental CI provenance
corrects the original report's generic concurrent-timing wording.

Keep the upstream context settings. Sparse reused fixtures do not establish a
full-corpus cost for this channel. Remaining platform numerical differences
change byte deltas but not these rejection decisions. Subsequent frozen tests
investigate adaptive depth and model-neuron permutation separately; do not
combine them with these rejected changes.

## Adaptive-depth follow-up on canonical inputs

The separate frozen depth protocol changes the cascade skip threshold from 8
to 9 or 31 (unreachable after the ±30 gate clamp). Mac results are:

| Threshold | Screen payload | Delta | Disjoint payload | Delta |
| --- | ---: | ---: | ---: | ---: |
| 8 | 119,065 | — | 117,438 | — |
| 9 | 119,071 | +6 | 117,436 | −2 |
| 31 | 119,084 | +19 | 117,451 | +13 |

[Both](../../../benchmarks/model-variants/20261017-depth-screen-v1/report.json)
[comparisons](../../../benchmarks/model-variants/20261017-depth-holdout-v1/report.json)
pass original-byte restoration and context checks. Neither candidate advances;
no reserved-range scores were read. More cascade computation changes online
learning state too, so a size gain was not guaranteed. Native Linux comparisons
were launched separately before these results. Timing remains exploratory.
