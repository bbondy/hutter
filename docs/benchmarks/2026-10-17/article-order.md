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
  --output build/order-screen-v1
python3 scripts/article_order.py prepare \
  --enwik8 data/enwik8 --build build/native-parity-v1 \
  --output build/order-holdout-v1 --start-offset 49000000 --role holdout
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
the prompt code uses the latter to choose metadata placement. The running
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
