---
title: The integer arithmetic coder
description: Follow inclusive ranges, emitted bits, decoder targets, and termination in the byte PPM implementation.
---

# The integer arithmetic coder

The [arithmetic-coding chapter](../foundations/arithmetic-coding.md) uses fractions to explain the idea. This page follows the finite-integer implementation in [`src/byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs). It is implementation detail, not a prerequisite for the earlier codec chapters.

## From fractions to an integer range

`ArithmeticEncoder` stores `low` and `high`. Both ends are **inclusive**: a range `[0, 255]` contains 256 integer positions. The Rust coder starts at `[0, 2³² − 1]`; `STATE_BITS` is 32. It uses `u64` values for `low`, `high`, and the intermediate products so that multiplying the range by a frequency does not require a fractional number.

For a range of size `range = high − low + 1`, the selected outcome occupies:

```text
new_low  = old_low + floor(range × cum / total)
new_high = old_low + floor(range × (cum + freq) / total) − 1
```

`floor` means discard any fractional part. `cum` counts outcomes before the selected one; `freq` is its count; `total` is the count of all possible outcomes, including an escape when present. The `− 1` is needed because `high` is inclusive. The encoder rejects zero frequencies and ranges that do not fit inside `total`.

## A small numerical trace

Use eight state bits just for this example, so the starting range is `[0, 255]`. Keep a fixed model with counts `A:3`, `B:1`: `A` uses `(cum=0, freq=3, total=4)` and `B` uses `(cum=3, freq=1, total=4)`.

| Event | Calculation | Range selected before emitting bits |
| --- | --- | --- |
| Start | 256 available positions | `[0, 255]` |
| Code `A` | Keep the first `3/4` of 256 positions | `[0, 191]` |
| Code `B` | Keep the last `1/4` of 192 positions | `[144, 191]` |

`[144, 191]` lies entirely in the upper half of `[0, 255]`, so the coder can emit a leading `1`. It subtracts 128 and doubles the remaining range, giving `[32, 127]`. That range lies entirely in the lower half, so it can emit `0` and double again, giving `[64, 255]`. The settled prefix is `10`. The real coder then finalizes the remaining range; with the same eight-bit version of its finish rule, it would emit `1010` and pad the byte to `10100000`. This is a toy trace, not the byte sequence written by the actual 32-bit adaptive PPM codec.

## Why renormalization works

The 32-bit coder checks three cases after each range update:

| Case in `encode` | Meaning | Action |
| --- | --- | --- |
| `high < HALF` | Entire range is in the lower half. | Emit `0`, then shift and expand the range. |
| `low >= HALF` | Entire range is in the upper half. | Emit `1`, subtract `HALF`, then shift and expand. |
| `low >= QUARTER && high < THREE_QUARTERS` | Range is trapped in the middle half; a leading bit is not settled. | Record a pending bit, subtract `QUARTER`, then shift and expand. |

In the middle case, often called **underflow**, `emit_bit` writes the pending bits later as the opposite of the next settled bit. The decoder performs the same shifts and subtractions, so it stays on the same interval. Repeated renormalization prevents the integer range from shrinking to zero after a long sequence.

## The decoder's matching step

`ArithmeticDecoder::new` fills its `code` value from the first 32 payload bits; `BitReader` supplies zero bits after the payload ends. Before selecting an outcome, `target(total)` maps that `code` point into one of the `total` frequency positions. The model finds the symbol whose cumulative interval contains the target. `consume(cum, freq, total)` then applies the same `new_low` and `new_high` formulas as the encoder and performs matching renormalization.

In the eight-bit example, a code value of `160` lies inside `[144, 191]`. With the initial range, `target(4)` is `2`, which selects `A`'s positions `0`–`2`. After consuming `A`, the range is `[0, 191]`; the next `target(4)` is `3`, which selects `B`. Both sides must also use the same model counts **before** each step. The [byte PPM walkthrough](ppm-walkthrough.md) shows the separate `observe` call after coding or decoding a symbol.

## Termination and archive validation

`finish` writes enough final bits to identify a value in the remaining range; `BitWriter::finish` pads a partial byte with zero bits. Byte PPM's archive header records the original byte length, so the decoder stops after that many bytes, not when it sees a special end symbol. An empty payload or truncated payload is not automatically detected by the arithmetic bit reader, because it returns zero after running out of bits. A successful round trip establishes that the paired encoder and decoder agree; it is not a general proof that every damaged payload is rejected.

The entry points to inspect are `ArithmeticEncoder::encode`, `ArithmeticEncoder::finish`, `ArithmeticDecoder::target`, and `ArithmeticDecoder::consume` in `src/byte_ppm.rs`. The same source file contains `BitWriter` and `BitReader`, which turn individual bits into payload bytes and back.
