---
title: From prisoner cycles to article ordering
description: Test whether arranging linked Wikipedia articles improves compression, with exact reconstruction and saved controls.
---

# From prisoner cycles to article ordering

The 100 prisoners puzzle suggests a useful research question: can following
relationships in the input expose structure that a compressor can use? Our first
test changes Wikipedia article order so that more incoming links appear before
the article they describe. The measured archive size decides whether this helps.

The completed tables below use the earlier Mac entity representation. A later
[full-stream check](native-parity.md) found and fixed an inherited arithmetic
portability defect. Fresh comparisons preserve these same pages and algorithms
while using prepared bytes that match Linux; earlier round trips remain saved.

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

The disjoint fixture's corrected-phase comparison is now verified below.
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
prefix length when it is nonempty.

All six corrected comparisons restore the original articles exactly:

| Order | First fixture payload | Change | Disjoint fixture payload | Change |
| --- | ---: | ---: | ---: | ---: |
| Source | 119,969 bytes | — | 118,411 bytes | — |
| Graph | 119,975 bytes | +6 bytes | 118,433 bytes | +22 bytes |
| Random | 120,083 bytes | +114 bytes | 118,646 bytes | +235 bytes |

The [first-fixture record](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-screen-v3/report.json)
and [disjoint record](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-holdout-v3/report.json)
retain every trial. Graph order actually feeds more link-prefix tokens: **2,897
instead of 2,319**, and **1,531 instead of 1,359**. Yet both payloads grow.
This is stronger evidence than counting graph edges alone, but order also changes
the other models' context, so it does not isolate what the link channel gains.
The [fixed-order model tests](link-context.md) address that next question.

Encoder and decoder context counters match, and all runs enter main text.
A repeat with telemetry disabled produces the identical 119,969-byte baseline
archive. These results establish corrected native fixture baselines; they do
not promote this graph heuristic or establish a full-submission improvement.

## Reconstructing the competitive order

We have now run the pinned census, comment-index and article-order stages on the
full, checksum-verified enwik9 file using a native Mac helper. The resulting
**998,030,918-byte reordered main stream matches upstream's recorded digest**.
All 243,425 page IDs are accounted for. The
[saved validation](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-upstream-order/validation.json)
records the hashes and process measurements. This validates those stages; no
full-corpus compressed size is claimed.

An important detail emerged: the 71,148-page front block contains 71,110 redirects
and 38 excluded ordinary pages. Calendar pages and five other page classes also
have prescribed placements. The next comparison projected this
exact order onto the same frozen article sets. One candidate makes a few adjacent
link-guided swaps; another applies the graph heuristic within ordinary-page
regions. Both preserve special positions and full-order class-region boundaries.
The [protocol](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-projection-protocol-v1/protocol.json)
was frozen before measuring. Even this projection omits surrounding corpus
context, so a fixture improvement still needs full-pipeline confirmation.

Its first verified results were:

| Order | First fixture payload | Change | Disjoint fixture payload | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream projection | 119,868 bytes | — | 118,442 bytes | — |
| Local swaps | 119,884 bytes | +16 bytes | 118,438 bytes | −4 bytes |
| Graph within regions | 119,896 bytes | +28 bytes | 118,456 bytes | +14 bytes |

All six restore the original articles. The
[screen](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-projected-screen-v1/report.json)
and [disjoint report](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-projected-holdout-v1/report.json)
retain the evidence. Neither candidate improves both fixtures. The subsequent
entity correction requires fresh baselines, with exactly the same permutations;
it is not a newly tuned ordering candidate.

## Results with canonical entity preprocessing

The same frozen permutations have now been rerun after the portability fix:

| Order | Screen payload | Change | Disjoint payload | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream projection | 119,065 bytes | — | 117,438 bytes | — |
| Local swaps | 119,073 bytes | +8 bytes | 117,427 bytes | −11 bytes |
| Graph within regions | 119,096 bytes | +31 bytes | 117,476 bytes | +38 bytes |

All six restore the original articles and pass actual context-counter checks.
The [canonical screen](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-projected-screen-v2/report.json)
and [canonical disjoint comparison](https://github.com/bbondy/hutter/blob/main/benchmarks/article-order/20261017-projected-holdout-v2/report.json)
retain the evidence. Neither candidate improves both fixtures, so neither
advances to the reserved third range or a Linux ordering comparison. These are
Mac fixture payloads, not estimates of a full-corpus ordering gain. More forward
links alone is not a sufficient objective for the frozen model.

## Limits that matter before promotion

The earlier source-order tables and the competitive-order projections answer
different questions. The canonical projection above is the relevant baseline
for these proposed changes to upstream ordering.

Code inspection found that the legacy development runner retained the full corpus's
fixed **71,148-page redirect-block boundary**. Every legacy small fixture remained inside
that block. Non-redirect text can still round-trip through its escaped form,
and link processing remains present, but pages after the first receive a four-token
`#rd` redirect-block prompt. That differs from the main-text phase of a full
submission. These results must be identified
as experiments with that inherited boundary. The v3 results above correct the
fixture phases and verify actual context-token measurements. The implementation
and acceptance checks are tracked in
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

The canonical upstream-order comparison rejects both ordering candidates.
The separate [controlled link-context tests](link-context.md) also reject all
three reduced-context settings on Mac and Linux. Continue with a different
predeclared model hypothesis; any promising candidate still needs independent
confirmation, Linux ranking and, if justified, matched retraining. A third enwik8 range starting at byte
80,000,000 is reserved before selection; the repeatedly used disjoint set is
not untouched validation.
Only a full enwik9 round trip with packaged size and resource measurements can
support a prize claim. The [experiment playbook](experiment-playbook.md) explains
how these gates fit the broader research plan.
