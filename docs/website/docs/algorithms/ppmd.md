---
title: PPMD and exclusion
description: Understand PPMD-style byte backoff, symbol exclusion, and the bitwise forms in this repo.
---

# PPMD and exclusion

The ordinary [byte PPM](byte-ppm.md) codec backs off from a long context to a shorter one by coding an **escape**. But consider a byte that the long context has already seen. If the encoder escaped from that long context, the actual byte cannot be one of those seen values. The shorter context can avoid assigning probability to them. This is **exclusion**.

The `ppmd` codec in [`src/ppmd.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd.rs) uses byte contexts up to order 6. At each context it filters out excluded symbols, codes the target if present, or codes an escape and adds that context’s symbols to the excluded set. If all shorter contexts escape, an order-minus-one step chooses uniformly among still-available byte values. Encoder and decoder build the same exclusion set as they descend.

```text
long context knows {A, B}; target is C
→ code escape; exclude A and B
short context knows {A, C, D}
→ code C among the eligible values C and D
```

Without exclusion, the short context would still spend part of its probability on `A`, even though escaping the long context already told the decoder the target was not `A`. Exclusion uses information the decoder has already received. The decoder builds the same excluded set as it reads escapes; it does not need a separate list in the archive. If no context can code the byte, the final fallback chooses among byte values not yet excluded, so a new byte remains possible.

The change can be made numerical without following the arithmetic coder. Suppose the long context has counts `A:3, B:1` and the shorter context has `A:5, B:1, C:2, D:1`. The target is `C`. In this implementation the long context has escape frequency `1`, so it first codes an escape from a total of `3 + 1 + 1 = 5`. It then excludes `A` and `B`. The shorter context now has eligible counts `C:2, D:1` plus escape frequency `1`; `C` occupies `2` of those `4` frequency positions. Without exclusion, `C` would occupy only `2` of `11` positions in that shorter context, because counts for `A`, `B`, and a larger escape remain. These shares are conditional at the shorter-context step; the long-context escape has its own cost too.

The actual code computes these totals in `Context::stats`, removes known symbols with `Context::exclude_all`, and uses `encode_order_minus_one` only when no context supplies the byte. The example counts are a possible model state, not a claim about a specific input file.

This is a **PPMD-style experiment** in this repository, not a claim of byte-for-byte compatibility with external PPMd programs or file formats. Its archive signature is `PPMD`.

## Two ways to feed bits from a byte model

`ppmd-bit` in [`src/ppmd_bit.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd_bit.rs) first builds a distribution over next **bytes** using PPMD-style exclusion. To code each bit, it filters that byte distribution by the bits already seen in the current byte and sums the mass for possible next `0` and `1` bits. It updates the byte model after all eight bits are known. Its archive magic is `PDBT`.

`ppmd-mix` in [`src/ppmd_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd_mix.rs) takes this one step further. A PPMD byte predictor contributes a next-bit probability alongside direct bit-history predictors. A mixer combines them and adapts weights while decoding or encoding. Its archive magic is `PDMX`.

**Read it in code:** compare `ppmd.rs`’s `Model::encode_symbol` and `Model::decode_symbol`, especially where each updates `excluded`. Then inspect `ppmd_bit.rs`’s `BitModel::bit_probability` to see how a next-byte distribution becomes a next-bit probability.

`ppmd`, `ppmd-bit`, and `ppmd-mix` are independent archive formats. The `make roundtrip` target can verify each; the decompressor identifies them by their headers rather than by a command-line codec name.

**Next:** [How models mix predictions](mixing.md).
