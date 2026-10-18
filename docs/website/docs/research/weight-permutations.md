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

The submission carries two copies of this container. The best result therefore
suggests a gross saving of 8,560 bytes before measuring the rebuilt executables
and their binding data. It is a small component improvement, far from a complete
prize-winning margin, and is not yet a packaged score.

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

These are bounded block tests, not full-compressor results. Next checks are
native Linux kernels, complete coder archives and exact original-byte restoration
with the best container, followed by rebuilding and counting the complete
submission. The model's fingerprint check stays active: each experimental
binary must explicitly bind its intended container.
