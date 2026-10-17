---
title: From prisoner cycles to article ordering
description: Test whether arranging linked Wikipedia articles improves compression, with exact reconstruction and saved controls.
---

# From prisoner cycles to article ordering

The 100 prisoners puzzle suggests a useful research question: can following
relationships in the input expose structure that a compressor can use? Our first
test changes Wikipedia article order so that more incoming links appear before
the article they describe. The measured archive size decides whether this helps.

## What transfers from the puzzle

In the puzzle, each numbered box points to another box, so the arrangement is a
permutation made of disjoint cycles. Starting at your own number and following
the pointers finds your number if its cycle fits within the opening limit.
The strategy changes the prisoners' chances of succeeding together; it does not
make an arbitrary permutation require fewer bits to describe. Richard Stanley's
[algebraic combinatorics notes](https://math.mit.edu/~rstan/algcomb/algcomb.pdf)
describe the cycle argument.

Compression needs a reversible representation that lets the next model make
better predictions. The [Burrows–Wheeler transform](https://www.cs.jhu.edu/~langmea/resources/burrows_wheeler.pdf)
is a related, established example: sort rotations, retain their last column and
enough information to invert the transform. For `banana$`, that column is
`annb$aa`. The output still contains seven characters; a later coder benefits
from the grouping. This is precedent for testing a reversible rearrangement,
not evidence that the prisoners' strategy is a new compressor.

## Why Wikipedia links could help

Suppose **B links to A**. Encoding B before A makes B's mention of A available to
both the encoder and decoder when they reach A. Upstream cmix-neif can supply
earlier link context to its transformer. Its current article order already groups
similar pages using an inherited embedding-derived order, plus special handling
for redirects and other page classes.

Wikipedia is not a permutation: pages can have many outgoing links, many incoming
links, or none. A cycle also imposes a limit. For `A → B → C → A`, any linear
order leaves at least one link pointing to an already processed page. We group
mutually reachable pages, put the groups in dependency order, and use a stable
greedy rule to arrange the pages inside each group. It is a heuristic, not an
optimal-order claim.

The upstream author explicitly lists ordering for greater link-context
availability as untested and notes the possible need for transformer retraining.
See the imported [README's link-context and article-order sections](https://github.com/bbondy/hutter/blob/main/engines/cmix-neif/README.md).

## The controlled experiment

We froze the algorithm, random seed and two article sets before measuring their
compressed sizes. Each set has three variants: source order, graph order and a
deterministic random-order control. Every variant contains exactly the same raw
pages. The existing model weights, dictionary and native binary stay fixed.

| Fixture | Raw bytes | Pages | Internal link pairs | Earlier links: source / graph / random |
| --- | ---: | ---: | ---: | ---: |
| Previous tiny fixture | 117,161 | 19 | 0 | 0 / 0 / 0 |
| First 1 MB fixture | 1,033,597 | 172 | 66 | 42 / 54 / 35 |
| Disjoint 1 MB fixture | 1,005,977 | 138 | 63 | 31 / 38 / 31 |

The old tiny fixture cannot exercise this hypothesis: none of its pages link to
each other under our exact-title matching rule. Reusing the larger contiguous
fixture is more useful than choosing a special collection of well-connected
pages. The disjoint set begins at byte 49,000,139 of the checksum-verified enwik8.

These counts are a **graph proxy**, not measured transformer context. We unescape
XML and match titles exactly, removing link fragments and display text. We do
not resolve redirects or normalize capitalization and underscores. The actual
model matches token sequences, has context limits and can match title prefixes.
On the first larger fixture, graph order adds twelve forward links but only two
additional pages gain any prior incoming link: 26 instead of 24.

There are also 11 reciprocal pairs: if A links to B and B links to A, one link
must point backward. This caps the first fixture at at most 55 forward links;
the heuristic reaches 54. Near-maximizing that proxy still need not improve
compressed size.

A graph-only audit of all **12,346 complete pages in enwik8** finds a mutually
reachable component containing **5,726 pages**. Grouping cycles therefore leaves
a substantial internal-order problem. The
[saved audit](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-graph-audit-v2/enwik8.json)
records its source bounds and hashes. This was not a full-corpus compression run.

## How the decoder restores the original

All selected source pages have unique, increasing page IDs. After decoding and
inverting preprocessing, sorting by those IDs restores the original bytes.
The decoder does not need the graph or a stored permutation. The preparation
tool refuses a fixture that does not satisfy this assumption.

For these fixtures the explicit order side data costs zero bytes. The code that
restores order and any required encoder code still belong in the final package
accounting. Our fixture numbers exclude the executable, dictionary and weights
and are **not Hutter Prize submission scores**.

## What the fast controls show

We first compressed the same prepared streams with three standard codecs. All
18 prepared-stream decoder checks passed.

| Codec | Graph − source, first fixture | Graph − source, disjoint fixture |
| --- | ---: | ---: |
| zlib level 9 | −571 bytes | −874 bytes |
| bzip2 level 9 | +2,542 bytes | +156 bytes |
| XZ preset 9 | −136 bytes | +36 bytes |

Negative means smaller. Ordering is not uniformly beneficial: it can improve one
model's locality while hurting another's. These controls do not have cmix's
link-context model and cannot establish what causes a cmix improvement.

## Legacy native cmix screen

All three native decoders passed. Inverse preprocessing and page-ID sorting then
restored the same **1,033,597 original bytes** for every variant. The
[verified comparison](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-screen-v1/report.json)
retains the hashes, manifest and process logs. These are single trials; repeated
encoding determinism and Linux candidate ranking were not tested here.

| Order | Payload bytes | Change from source |
| --- | ---: | ---: |
| Source | 120,337 | — |
| Graph | 120,359 | +22 bytes (+0.018%) |
| Random | 120,936 | +599 bytes (+0.498%) |

The tested graph heuristic does not improve the first fixture, despite its
higher forward-link count. This does not settle whether better ordering can
help the full compressor. It rejects the shortcut of treating more available
links as evidence of fewer compressed bytes.

The disjoint fixture is prepared and its standard-codec controls are saved.
Its corrected-phase cmix comparison is now running, as described below.
“Disjoint” means separate from the experiment's first sample; it does not mean
unseen by the inherited pretrained weights. No model or order was retuned from
these measurements.

## Corrected phase experiment

The new fixture mode declares both the total article count and the length of the
redirect prefix. It applies the same boundary in the preprocessor and model,
and writes the counts in a 16-byte development header. The decoder rejects a
configuration mismatch before pretraining. Those 16 bytes count toward every
reported fixture payload.

We kept the same two raw article sets. Each order now starts with the same
redirect pages in source order; only ordinary articles move. The screen contains
127 redirects and 45 ordinary articles. The disjoint fixture contains 28 redirects
and 110 ordinary articles. The graph algorithm operates on the movable ordinary
subgraph; the random seed stays fixed. This creates a new baseline rather than
revising the historical measurements.

The model now reports actual incoming-link prefix tokens fed, redirect prompts
and alias context. Verification requires equal encoder/decoder counters, the
expected number of redirect prompts and entry into main text. The first runtime-only correction caught another issue: the standalone phda9
helper still used the release cutoff and added unnecessary escapes to ordinary
article bodies. That batch is retained as rejected diagnostic evidence.

The [v3 protocol](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-protocol-v3/protocol.json)
passes the same phase settings through preparation, encoding, decoding and inverse
preparation. Tests cover zero, mixed and all-redirect prefixes and exact raw
restoration. Upstream emits prompts after page separators, so the first page
receives no redirect prompt; the expected count is one fewer than the redirect
prefix length when it is nonempty. The new comparisons are running, with a
telemetry-disabled repeat to check that collecting counters preserves the archive.

## Limits that matter before promotion

The baseline here is **source order**, not upstream's competitive embedding order.
A win over source order would justify a better-controlled next experiment.

Code inspection found that the legacy development runner retained the full corpus's
fixed **71,148-page redirect-block boundary**. Every legacy small fixture remained inside
that block. Non-redirect text can still round-trip through its escaped form,
and link processing remains present, but every page also receives a four-token
`#rd` redirect-block prompt. That differs from the main-text phase of a full
submission. These results must be identified
as experiments with that inherited boundary. Correct fixture phase boundaries
and actual context-token measurements are prerequisites for stronger conclusions.
The concrete implementation checks are tracked in
[issue #13](https://github.com/bbondy/hutter/issues/13).

Further limitations are frozen weights trained on another order, very sparse
within-sample links, and the native/Linux numerical differences described in
[the parity report](native-parity.md). The current greedy cycle routine also
needs a scalability review before applying it to a large strongly connected
component in enwik9.

## Keep the evidence and choose the next experiment

The [research protocol and saved records](https://github.com/bbondy/hutter/blob/main/docs/benchmarks/2026-10-17/article-order.md)
retain source ranges, page hashes, all permutations, graph counts, binary and
asset hashes, and codec results. The comparison verifier additionally checks
the actual archive, decoded prepared bytes, inverse preprocessing and restoration
to the common original byte stream. It refuses different models or article sets.

```bash
python3 scripts/order_history.py list
```

The next gates are correct fixture boundaries; a comparison against upstream's
actual order with local changes that preserve its topical groups; actual supplied
context counts; then Linux confirmation and, if justified, matched retraining.
Only a full enwik9 round trip with packaged size and resource measurements can
support a prize claim. The [experiment playbook](experiment-playbook.md) explains
how these gates fit the broader research plan.
