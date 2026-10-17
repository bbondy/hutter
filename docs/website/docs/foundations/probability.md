---
title: Probability and surprise
description: Why a good prediction costs fewer bits, and how to interpret entropy without prerequisites.
---

# Probability and surprise

A **probability** is a number from `0` to `1` describing how likely an outcome is. `3/4`, `0.75`, and `75%` mean the same thing: three chances out of four. A probability is a prediction, not a guarantee.

If a sample contains `AAAB`, the observed **frequency** of `A` is three and of `B` is one. Dividing by the four observations gives estimates `P(A) = 3/4` and `P(B) = 1/4`. Here `P(A)` means “the probability assigned to `A`.” Counts from a finite sample are estimates; future data can differ.

## From a prediction to a bit cost

When two outcomes are equally likely, one bit can distinguish them. When one out of four equally likely outcomes occurs, two bits can identify it. Halving the probability adds roughly one bit to the ideal coding cost:

| Probability assigned to the actual outcome | Ideal cost |
| --- | ---: |
| `1/2` | 1 bit |
| `1/4` | 2 bits |
| `1/8` | 3 bits |
| `3/4` | About 0.42 bits on average |

The general rule is `−log₂(p)` bits for an outcome assigned probability `p`. “Log base 2” asks how many factors of two correspond to a number; for example, `log₂(8) = 3` because `2 × 2 × 2 = 8`. It gives the costs above. You need not calculate logarithms to follow the codecs: the practical rule is **assign more probability to the outcome that actually occurs**.

A physical archive contains whole bits and bytes, not a fraction of one bit. The fractional figure is an *average or ideal contribution* across a sequence. [Arithmetic coding](arithmetic-coding.md) combines many predictions so its total can approach that ideal; a Huffman code gives each symbol a whole-number code length.

## Previous data changes the estimate

The bytes `ABABAB` contain three `A`s and three `B`s, so a model ignoring position gives each about half the probability. But among positions followed by another byte, every `A` is followed by `B`. This is a different, more specific count:

| Previous byte | Observed next byte | Count |
| --- | --- | ---: |
| `A` | `B` | 3 |
| `B` | `A` | 2 |

The last `B` has no next byte in this sample, so it adds no next-byte observation. The previous byte is an **order-1 context**. An order-3 byte context uses the previous three bytes. A longer context may predict well when it has repeated, but may have no observations at all. A PPM model can then **back off**, meaning it uses a shorter context. An escape event tells the decoder that the longer context did not supply the value.

An unseen value must not become impossible. If a model assigned it probability zero, a coder could not represent it. The repository's PPM codecs keep escape and fallback paths for this reason. This is a format requirement, not just a way to improve compression.

## What entropy measures

**Entropy** is the average ideal cost under a set of outcome probabilities. With `P(A) = 3/4` and `P(B) = 1/4`, it is `3/4 × 0.42 + 1/4 × 2`, or about `0.81` bits per symbol. This is a reference for a source with those probabilities, not a promise that a four-byte file becomes a one-byte archive. A real archive must also identify its format, terminate correctly, and account for its model.

The **model** supplies counts or probabilities. The **coder** turns its choices into bits. Keeping those two jobs separate makes the later algorithms easier to compare: Huffman derives code paths from counts, while most PPM variants pass probability ranges to an arithmetic coder.

**Next:** [Prefix codes](prefix-codes.md) builds an unambiguous code from frequencies.
