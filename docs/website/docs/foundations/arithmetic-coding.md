---
title: Arithmetic coding
description: Turn a sequence of changing probabilities into bits using an interval shared by encoder and decoder.
---

# Arithmetic coding

Huffman coding assigns each symbol a bit string of whole-number length. **Arithmetic coding** instead identifies a *sequence* by repeatedly narrowing a range of numbers, called an **interval**. This can approach the fractional average costs discussed in [probability and surprise](probability.md).

The notation `[0, 1)` means “from zero, including zero, up to one, excluding one.” Suppose a model assigns `A` probability `3/4` and `B` probability `1/4`. Start with `[0, 1)` and give its first three quarters to `A`: `[0, .75)`. Give the remaining quarter to `B`: `[.75, 1)`. If the actual first byte is `A`, keep only `[0, .75)`.

For the second byte, split that *smaller* interval by the same fractions. Its upper quarter is `[.5625, .75)`, because one quarter of `.75` is `.1875`. If the second byte is `B`, that becomes the new interval:

| Step | Interval kept |
| --- | --- |
| Begin | `[0, 1)` |
| Encode `A` | `[0, .75)` |
| Encode `B` | `[.5625, .75)` |
| Encode another `A` | `[.5625, .703125)` |

For the third `A`, the current interval has width `.1875`; its first three quarters have width `.140625`, giving the last row. A number such as `.625` is inside both the `AB` and `ABA` intervals. The decoder therefore needs to know *how many symbols* to recover as well as the code point and model. It sees `.625` in `A`'s first range, then `B`'s second range, then `A`'s third range. Numbers inside an interval can be written in binary: `.625` is `.101` in base two because it equals `1/2 + 0/4 + 1/8`. That connects the interval to bits. The archive's original length supplies the number of output bytes in this repository's byte-coded formats. `.625` is a mathematical illustration, not the exact payload emitted by a Rust codec.

## Counts specify the split

The model does not have to pass fractions to the coder. For counts `A:3` and `B:1`, ordered `A` before `B`, it can pass integer triples:

| Outcome | `cum` | `freq` | `total` | Share of current interval |
| --- | ---: | ---: | ---: | --- |
| `A` | 0 | 3 | 4 | From `0/4` to `3/4` |
| `B` | 3 | 1 | 4 | From `3/4` to `4/4` |

`cum` is the count of outcomes *before* this one, `freq` is this outcome's count, and `total` is the sum of all counts. `encoder.encode(cum, freq, total)` selects that share of the current interval. An **escape** is simply another possible outcome with its own range; after an escape, the model tries a fallback distribution.

The decoder uses the same counts to identify which share contains the encoded value, then narrows its interval in the same way. It must make the same model updates after each decoded value. If either side changes the outcome order, counts, or update time, the same bits will point to different symbols.

## Finite arithmetic in the Rust code

Real compressors cannot store infinitely precise fractions. The arithmetic coders in this repository keep bounded integer `low` and `high` values. When the leading part of the interval is settled, they emit bits and **renormalize**: they shift and expand the remaining range so coding can continue. The decoder performs matching integer operations. The payload also needs a finalization rule and may contain padding; the recorded original length tells the decoder when enough bytes have been reconstructed.

Calls such as `encoder.encode(cum, freq, total)` appear in [`src/byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs). The coder does not decide which byte is likely; the model does. The coder turns the model's ranges into bits.

The [integer arithmetic-coder walkthrough](../codebase/arithmetic-coder.md) follows the actual bounded-range equations and emitted bits. It is optional implementation detail; the interval example above is enough to understand why a model's probabilities matter.

On decode, `target(total)` asks which part of the current range contains the encoded value; `consume(cum, freq, total)` makes the same narrowing step. The decoded byte or bit is then observed by the model before the next prediction.

**Next:** [Byte PPM](../algorithms/byte-ppm.md) supplies the changing counts that this coder uses.
