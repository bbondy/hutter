---
title: Reorder a model without changing its predictions?
description: Use hidden-neuron symmetry to reduce stored weights, with exact kernel checks before compressor claims.
---

# Reorder a model without changing its predictions?

Hidden neurons have an arbitrary numbering. If we move a neuron and also move
the corresponding connection in the next layer, the mathematical network stays
the same. That gives us freedom to choose a numbering that is easier to store.

For an MLP block written as `D · f(U · x)`, permute the rows of `U`, their
individual scales, and the matching columns of `D`. The elementwise function
`f` follows the moved neurons. The final sum therefore combines the same values
with the same weights.

This connects the earlier [permutation and cycle discussion](article-order.md)
to a different object: the model itself. We are choosing among equivalent
neuron labelings. The decoder receives the resulting model directly; it does
not need a table restoring our preferred neuron names. This does not create a
general shortcut for compressing arbitrary data.

## The first container comparison

The existing weight coder adapts to nearby values. We froze three simple
ascending sort keys for each MLP layer, retaining the previous order for ties:

| Neuron order | Container bytes | Change per copy |
| --- | ---: | ---: |
| Original | 3,716,667 | — |
| Absolute up-row scale | 3,712,387 | −4,280 |
| Number of zero up-row weights | 3,714,991 | −1,676 |
| Sum of up-row weights | 3,715,729 | −938 |

The [saved results](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-container-permutations-v1/report.json)
include every candidate and its permutation map. Rewriting the unchanged model
first reproduced the original container byte for byte. Every new container
reads back to exactly its intended tensors, and inverse permutations recover
the original tensors. No corpus scores selected these orderings.

The submission carries two copies of this container. The initial gross estimate
was an 8,560-byte saving. Real native Linux release builds now confirm that
component delta below. It is a small improvement, far from a complete
prize-winning margin, and is not a full-corpus score.

## Mathematical symmetry needs implementation checks

Floating-point reductions can depend on operation order. Here the down
projection sums bounded integers before its floating-point epilogue, which
makes exact preservation plausible. We still test the actual compiled kernels.

On the Mac, all three candidates pass 1,024 synthetic input vectors in each of
16 MLP layers: 16,384 block cases per candidate. Tests include activation-range
extremes and force both sparse and dense down-projection paths. All output bits
and nonzero counts agree. An identity control passes; a deliberately broken
model is rejected at the first layer. The
[kernel evidence](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-native-kernels-v1/report.json)
records compiler flags, source hashes and logs.

The model's fingerprint check stays active: each experimental binary explicitly
binds its intended container. Mathematical symmetry alone does not authorize
turning that check off.

## Native Linux checks and measured package components

Native Ubuntu x86-64 recreated all three candidate containers byte for byte and
passed the same 16,384 sparse/dense block cases for each. The selected scale
ordering then produced **identical complete fixture archives**:

| Fixture | Original-container payload | Reordered-container payload | Archive SHA-256 |
| --- | ---: | ---: | --- |
| Screen | 119,067 bytes | 119,067 bytes | Identical |
| Disjoint | 117,426 bytes | 117,426 bytes | Identical |

All four trials restore the original XML and report the same context counters.
The [screen evidence](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-linux-screen-v1/report.json)
and [disjoint evidence](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-linux-holdout-v1/report.json)
include kernel reports, container hashes and CI provenance. Downloaded artifacts
were checked again locally, including inverse preparation to original XML.
These fixtures and bounded kernel cases do not prove equivalence on every input.

A separate native Linux job rebuilt both real release packages with upstream's
unchanged build script, PGO/LTO, section guards and actual unpacking checks:

| Component | Baseline | Reordered weights | Change |
| --- | ---: | ---: | ---: |
| Compressor executable | 3,999,867 bytes | 3,995,587 bytes | −4,280 bytes |
| Decoder prefix | 165,104 bytes | 165,104 bytes | 0 |
| Archive-side weight copy | 3,716,667 bytes | 3,712,387 bytes | −4,280 bytes |
| Sum of these components | 7,881,638 bytes | 7,873,078 bytes | **−8,560 bytes** |

The [package comparison](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-linux-packages-v1/comparison.json)
rechecks actual binaries and decoder-prefix bytes. It excludes the compressed
dictionary, full corpus payload, archive footer and invocation arguments.
A full score still requires the complete archive and resource measurements.
This was a native Linux build without Docker.

The rebuilt baseline is 822 bytes smaller than the published compressor and
has a different hash. This is a toolchain reproducibility question, not a gain
credited to our weight permutation. Nearly all listed reference packages match,
but the hosted image also has GCC 14 development files that Clang may select
instead of GCC 13. A separate controlled rebuild tests that explanation. Keep
same-host candidate deltas separate from published-binary reproduction.

## Where further weight savings could come from

An [audit of the unchanged container](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-container-audit-v1/README.md)
attributes every byte while reproducing the original file exactly. Int4 tensors
consume 3,629,108 bytes, or 97.6% of the container. The MLP up and down matrices
account for about 2.19 MB together.

For those int4 tensors, fitting an independent-symbol distribution to each
tensor gives a combined empirical entropy only about 2.2 KB below the current
coding cost. Fitting each row separately leaves about 54.9 KB **before storing
or learning the row distributions**. These fitted figures are not achievable
compressed sizes and are not limits on methods that exploit other dependencies.
They do suggest that another simple frequency-counter tweak has limited scope.
A larger gain needs stronger structure or model changes; retain this small
permutation improvement while testing those higher-impact hypotheses.
