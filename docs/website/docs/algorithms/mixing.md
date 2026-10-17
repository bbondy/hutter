---
title: Mixing predictions
description: Why several partial models can vote on the same next bit or byte.
---

# Mixing predictions

An order-1 context may have many observations but miss a long pattern. An order-6 context may be specific but scarcely observed. A **mixer** asks several models for predictions and combines them. It then changes their weights after seeing the actual byte or bit, so useful predictors gain influence.

Imagine two models estimating that the next bit is `1`. One says 60%; another says 90%. A mixer turns both into one probability for the arithmetic coder. The exact combination matters: changing the math changes every subsequent bit of the archive, so the decoder needs the same code and initial weights.

As a simple illustration, give the first prediction weight `1` and the second weight `2`. A weighted average is `(1 × 0.60 + 2 × 0.90) / (1 + 2) = 0.80`. This is a teaching example, not the exact formula or weights of every mixer below. The important requirement is that all contributing models describe the *same next outcome* and both encoder and decoder calculate the same combined probability.

## The mixed codecs here

| CLI codec | Inputs to its prediction | Source |
| --- | --- | --- |
| `ppm-byte-mix` | Byte PPM contexts of several orders | [`byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs) |
| `ppm-bit-mix` | Bit PPM contexts of several orders | [`ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm.rs) |
| `ppm-mix` | Bit-history models and byte-context models, both predicting the next bit | [`hybrid_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/hybrid_ppm.rs) |
| `ppmd-mix` | Bit-history models and a PPMD byte distribution converted to a bit probability | [`ppmd_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd_mix.rs) |
| `ppm-match-mix` | Byte-context models and a hashed match predictor | [`ppm_match_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm_match_mix.rs) |

For the bit mixers, a byte prediction becomes a bit prediction by summing the probabilities of bytes consistent with the current byte prefix. If the first bit is already `0`, only byte values beginning with `0` remain possible. The mixer works on the next bit, then repeats after observing it. `ppm-mix` uses weights per bit position, because the first bit of a byte and its last bit can have different useful predictors.

For example, if a toy byte model gives `0x41` three parts of probability and `0xC3` one part, the first bit is predicted as `0` with share `3/4`, because `0x41` begins with `0`; `0xC3` begins with `1`. After a first bit of `0`, the next-bit calculation considers only compatible bytes. Real codecs also preserve a way to code bytes the model did not list, rather than making them impossible.

## What the implemented bit mixer changes

The simple weighted average above explains the purpose but is not the formula in `ppm-mix`. In [`hybrid_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/hybrid_ppm.rs), `HybridMixer` first turns a probability `p` into **log-odds**, `ln(p / (1 − p))`. Odds compare the chance of `1` with the chance of `0`: `p = 0.8` gives odds `4`, while `p = 0.2` gives odds `1/4`. Their log-odds have equal magnitude and opposite signs. If two such predictions had equal weights and no other input, their contributions would cancel and the mixed probability would be `0.5`. The function `squash` turns the weighted log-odds sum back into a probability between zero and one.

After the actual bit is known, `HybridMixer::observe` adjusts weights based on the prediction error. A model that favored the actual bit tends to gain influence. Encoder and decoder observe the same bit at the same time, so they make the same weight update. Separate weights for each of eight positions allow a predictor to matter more for one bit position than another. This detail is optional for understanding the earlier weighted-average illustration, but it matters when changing this codec's source.

## Following one mixed bit

In `hybrid_ppm.rs`, read `HybridModel::predictions` to see the candidate probabilities, `HybridMixer::mixed_probability` to see their combined probability, and `HybridModel::observe_bit` to see weights and model state update after the actual bit. The decoder calls the same steps in the same order.

:::note[Mixing is still lossless]
The mixer may predict badly, making the archive larger, but a wrong prediction does not corrupt output. It simply costs more bits. Both sides still agree on the probability and on the decoded value.
:::

**Next:** [Match prediction](match.md), which turns repetition into a probability instead of a copy token.
