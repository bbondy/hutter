---
title: Byte PPM and context backoff
description: Predict a next byte from prior bytes, then fall back when a context has not seen it.
---

# Byte PPM and context backoff

**Prediction by partial matching (PPM)** asks: “When I last saw this context, what byte came next?” A context is recent history. In `ABABAB`, a one-byte context of `A` has repeatedly been followed by `B`. A higher order uses more preceding bytes and can make a more specific prediction, but it sees fewer examples.

The byte family in [`src/byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs) offers orders 1 through 6. The CLI name `ppm` is order 3. `ppm-o6` can use up to six prior **bytes**, not bits. Every version also has an order-0 table that counts bytes without context.

For `ABAB`, an order-1 model begins with no observations. After the first `A`, its order-0 table knows `A`. After the first `B`, it records that `B` followed `A`. After the second `A`, it records that `A` followed `B`. Before the final `B`, the previous byte is `A`, and the model can use the earlier `A → B` observation. This is why the update happens *after* each byte has been encoded or decoded: the decoder needs the same history when recording a transition.

`ABAC` shows a different case: the last byte is new even though its one-byte context already exists.

| Byte being coded | Previous byte | What the order-1 model knows beforehand | Coding path |
| --- | --- | --- | --- |
| First `A` | None | No counts yet. | Order-0 escape, then uniform `A`. |
| `B` | `A` | No `A` context has been observed yet. | Skip missing context; order-0 escape, then uniform `B`. |
| Second `A` | `B` | No `B` context has been observed yet. | Skip missing context; code `A` from order 0. |
| `C` | `A` | The `A` context has seen `B`, but not `C`. | Order-1 escape, order-0 escape, then uniform `C`. |

After the final row, observing `C` records `A → C` for future bytes. A **missing** context is skipped without an escape; an **existing** context that lacks the actual byte emits an escape. This distinction determines which arithmetic events the decoder must read.

The final `C` also gives a concrete count calculation. Before it, the order-1 context for `A` contains one `B`, so its escape has frequency `1` out of a total of `2` (`B` plus escape). Order 0 contains `A:2, B:1`; this implementation gives its escape frequency `2`, one for each distinct byte already seen, so that escape occupies `2` out of `5` positions. Finally, `C` is selected from 256 equally weighted byte values. The conditional shares multiply: `1/2 × 2/5 × 1/256 = 1/1280`. The ideal information cost of those events is about 10.3 bits. This is a calculation for *one byte's coding path*, not the exact number of payload bits or archive bytes emitted by the finite arithmetic coder.

## What happens for one symbol

The encoder checks the longest available context first. If that context contains the next byte, it arithmetic-codes the byte using the context’s counts. If the context exists but has *not* seen the byte, it codes an **escape event** and tries the next shorter context. If even order 0 has never seen the byte, it escapes again and codes the byte uniformly among all 256 values. “Uniformly” means every byte value gets the same share of this final range. The decoder reads the same sequence of events and discovers the byte at the same point; the fallback ensures even a completely new byte remains representable.

```text
order 3 has no 'x' → escape
order 2 has no 'x' → escape
order 1 has seen 'x' → code 'x' here
```

Missing contexts are simply skipped. This byte PPM implementation does not exclude symbols already seen at higher orders when it backs off; [PPMD](ppmd.md) adds that distinction. Context counts are updated **after** a byte is coded or decoded, and then history advances. The code rescales counts to keep arithmetic totals bounded.

## The mixed-order byte variant

`ppm-byte-mix` uses the same module but a different strategy. `MixedModel` gathers candidate probabilities from several byte orders, and `OrderMixer` combines them using weights that adapt as bytes are observed. An escape keeps unseen bytes possible. This is a separate archive format (`PPMX`), so the decoder knows to run the mixed model.

## Read it in the source

Follow `compress_with_order` → `Model::encode_symbol` → `Model::observe`; compare `decompress_with_order` → `Model::decode_symbol` → `Model::observe`. The two `observe` calls must see identical histories. Then compare `MixedModel::mixed_candidates` with the ordinary backoff loop.

The three names `ppm-o1`, `ppm`, and `ppm-byte-mix` select different model behavior and archive magic. The [byte PPM source walkthrough](../codebase/ppm-walkthrough.md) traces the ordinary order-1 case before introducing the mixed model. The `make roundtrip` target can verify each format; distinct `ARCHIVE` paths keep their results separate.

**Next:** [Bit PPM](bit-ppm.md), which asks the same question one bit at a time. For a source-level explanation of this module, read the [byte PPM code walkthrough](../codebase/ppm-walkthrough.md).
