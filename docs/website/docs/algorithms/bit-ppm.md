---
title: Bit PPM
description: Predict each bit from recent bits and understand bit-order names in the CLI.
---

# Bit PPM

The bit PPM family in [`src/ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm.rs) reads each input byte from its highest bit to its lowest. Before a bit is coded, the model checks recent **bit** contexts. Once decoded, that bit updates the model and bit history. Every eight decoded bits form one output byte.

The CLI names are `ppm-bit` (maximum order 8), `ppm-bit-o16`, `ppm-bit-o32`, and `ppm-bit-o64`. An order-8 bit context is the previous eight bits: approximately one byte’s worth of history, but it can cross byte boundaries. Order 64 uses up to 64 previous bits.

## One byte becomes eight decisions

The byte `A` is `01000001`. The bit model makes eight successive predictions. After coding the first `0`, that `0` becomes part of the context for predicting the following `1`. Coding one bit can require several arithmetic choices if a context escapes before a shorter context or the uniform fallback supplies the bit.

If another `A` follows, the first bit of that second byte is predicted using the bits already seen. With an order-8 limit, those are exactly the eight bits of the first `A`. After one bit of the second byte is processed, the most recent eight-bit context spans the end of the first byte and the beginning of the second. This is why “eight bits of history” is not always the same thing as “one previous byte” in a byte-oriented model.

There is a difference between *having a context in history* and *having a count for what followed it*. Before the first bit of the second `A`, the history has eight bits, but the model has not yet observed a next bit after that exact eight-bit sequence. It skips that missing context and backs off. If a third `A` begins, the same eight-bit history has an observation from the second `A`, so that context can participate. The shorter contexts may already have counts, and the order-0 fallback always allows a new bit to be coded.

An order-1 bit context makes the count updates easier to see. After the first `A` (`0 1 0 0 0 0 0 1`), the observed adjacent pairs are:

| Previous bit | Next bit | Times seen |
| --- | --- | ---: |
| `0` | `0` | 4 |
| `0` | `1` | 2 |
| `1` | `0` | 1 |

There is no `1 → 1` observation yet. The first bit of the *second* `A` is `0`, and the previous bit is the final `1` of the first byte. The order-1 table for `1` has seen `0` once, so it can code that bit directly. Observing this bit adds a second `1 → 0` example across the byte boundary. The next bit of the second byte is `1`; now the previous bit is `0`, whose table has seen four `0`s and two `1`s. This example follows only order 1; the actual `ppm-bit` encoder tries longer usable contexts first and may code the same bit at a higher order.

Like byte PPM, this model backs off through shorter contexts and an order-0 context. It uses escape events and a final uniform choice between `0` and `1`. A context can exist but still be skipped if `context_is_usable` decides it has too little evidence for its order. The separate `ppm-bit-mix` codec combines available order predictions instead of selecting the first usable one; its mixer keeps weights per bit position inside the byte.

## What changes for a developer

- `BitHistory` stores recent bits and forms lookup keys.
- `ByteBits` yields input bits; `ByteCollector` rebuilds output bytes.
- `Model` implements the backoff version; `MixedModel` and `OrderMixer` implement `ppm-bit-mix`.
- The archive magic differs for each maximum order (`PB08`, `PB16`, `PB32`, `PB64`) and for the mix (`PBMX`).

The same source file implements all these variants, but its decoder chooses behavior from the archive magic and calls the corresponding entry point. `make roundtrip CODEC=ppm-bit` verifies the order-8 format. Longer histories can cost more memory and time, and they do not guarantee a smaller archive.

**Next:** [PPMD and exclusion](ppmd.md), which changes how fallback probabilities are built.
