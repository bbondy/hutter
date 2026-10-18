---
title: Spend fewer bytes on the model?
description: Test whether a smaller predictor saves more model bytes than it adds to the compressed data.
---

# Spend fewer bytes on the model?

The [neuron-permutation experiment](weight-permutations.md) preserves the model's
mathematical function. Pruning deliberately removes neurons and changes its
predictions. The compressor can still be lossless: encoder and decoder use the
same smaller model, and the arithmetic code supplies the information that its
predictions miss. Every original XML byte must still come back exactly.

A smaller model does not automatically give a smaller submission. This engine
stores its weights twice. Removing weights saves those two copies, but worse
predictions can increase the payload for a billion bytes of input.

## Three choices fixed before coder measurements

The [protocol](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-pruning-protocol-v1/protocol.json)
ranks neurons within each MLP layer using the size of their incoming weights,
their scales, and their outgoing connections. The up-projection scale enters
quadratically because this model uses squared ReLU activations. This is a
heuristic, not a measurement of how often a neuron is useful. Rare features can
matter even when their weights look small.

Each candidate starts from the original model, removes a fixed fraction in
each layer and preserves the order of the surviving neurons. It changes no
other model parameter and is not combined with the permutation experiment.

| Removed per MLP layer | Neurons removed | Container bytes | Gross saving across two copies |
| --- | ---: | ---: | ---: |
| None | 0 | 3,716,667 | — |
| 5% | 606 | 3,608,196 | 216,942 bytes |
| 10% | 1,214 | 3,499,417 | 434,500 bytes |
| 25% | 3,050 | 3,170,384 | 1,092,566 bytes |

The [container records](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-pruning-containers-v1/report.json)
retain every removal map and ranking. The original container rewrites exactly;
each candidate reads back to its intended tensors. The upstream conservative
dead-neuron test finds no further provably dead neurons in the starting model,
so these removals must not be called function-preserving.

## Pay for worse predictions

Before reading any coder result, the
[archive protocols](https://github.com/bbondy/hutter/tree/main/benchmarks/weights/20261017-pruning-archive-protocol-v1)
freeze all three container hashes. On a one-million-byte raw fixture, the
5% candidate's gross budget is about 217 extra payload bytes. More than that
would consume its model saving if the penalty scaled proportionally to enwik9.
The 25% candidate has about 1,093 bytes of allowance on such a fixture.

That proportional estimate is only a screening rule. These fixtures start with
fresh model state and sparse projected article order; they do not predict the
full stream without error. The screen also excludes executable-size changes.
A candidate must fit its budget on both reused fixtures before larger/native
Linux confirmation, and eventually needs a complete packaged round trip.

## Measured outcome: reject all three unretrained candidates

All six Mac trials restore the original XML exactly and match their encoder
and decoder context counters. Each comparison also preserves the baseline's
input, order, dictionary, compiled sources and model settings except for the
declared weight container and its fingerprint. The predictions change, as
intended, and the payload penalty overwhelms the saved model bytes:

| Removed | Screen payload | Added bytes | Screen allowance | Disjoint payload | Added bytes | Disjoint allowance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 119,065 | — | — | 117,438 | — | — |
| 5% | 135,836 | +16,771 | 224.2 | 133,972 | +16,534 | 218.2 |
| 10% | 149,722 | +30,657 | 449.1 | 147,556 | +30,118 | 437.1 |
| 25% | 173,977 | +54,912 | 1,129.3 | 171,939 | +54,501 | 1,099.1 |

Allowances use each fixture's exact raw size, rather than rounding to one MB.
The penalties are roughly 49–76 times the allowed increases. **None advances
to native Linux, a larger sample or the reserved range under this protocol.**
The [saved decision](https://github.com/bbondy/hutter/blob/main/benchmarks/weights/20261017-pruning-screen-summary-v1/decision.json)
links and hashes all six complete records. Their `passed` field means the
round-trip and comparison checks passed; `within_gross_budget: false` records
the failed size screen. Concurrent timings are not speed measurements.

This rejects these fixed removals without retraining. It does not establish
that every smaller model loses. A later approach would need activation-aware
selection, compensation or retraining and a fresh exported-model comparison.
The immediate preparation step is to reproduce the upstream training-row dump
without transformer inference, so prompt coverage and any future training data
can be inspected. Generating that data is not itself a compression improvement.

## Check the implementation before blaming the model

A wrong kernel for narrower layers could also produce poor predictions while
still restoring losslessly. A separate
[frozen control](https://github.com/bbondy/hutter/tree/main/benchmarks/weights/20261017-pruning-control-native-v1)
compares each pruned model with a full-width model whose corresponding incoming
rows are zero. The latter retains all tensor shapes, scales and outgoing weights.
Both should compute the same MLP function for the same input.

All three pass 16,384 synthetic block cases each on the actual Mac kernels.
Retained quantized activations match after remapping, and the sparse and dense
routes produce identical residual float bits. The unmasked original fails the
comparison, as expected. This checks width packing and tail handling on those
inputs; it is not an all-input proof or a full-transformer comparison.

The result makes a simple width-handling bug less likely. It leaves the measured
size rejection intact and strengthens the case for studying actual activations
or retraining before removing more neurons.
