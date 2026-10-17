---
title: WikiMix-5
description: Tour the five predictor families in the repo’s experimental Wikipedia-oriented codec.
---

# WikiMix-5

Wikipedia text contains ordinary words and structured markup: tags, links, headings, numbers, and repeated templates. `wikimix5` asks five small models for likely next bytes and codes the result with arithmetic coding. Its archive magic is `WMX5`.

[`src/wikimix.rs`](https://github.com/bbondy/hutter/blob/main/src/wikimix.rs) contains an executable **experimental skeleton**. It can compress and decompress, but the [design note](https://github.com/bbondy/hutter/blob/main/docs/wikimix5.md) describes a more ambitious future mixer. Treat the current module and the design note as different stages of the project.

| Predictor | Intuition | Current code |
| --- | --- | --- |
| `BytePpmModel` | Recent byte contexts suggest a next byte. | Looks up contexts up to order 6 and order-0 counts. |
| `StructStateModel` | Markup syntax changes what bytes are likely. | Tracks a small syntax state and counts next bytes by state. |
| `WordModel` | Current word prefix and recent words can recur. | Hashes ASCII word context and counts next bytes. |
| `MatchModel` | A recent matching sequence may continue. | Hashes a short key and proposes continuation bytes. |
| `ClassModel` | Digits, letters, and other classes have patterns. | Tracks symbol classes with the syntax state. |

For each byte, `WikiMix5Model::predict` asks all five models. The current `Mixer` multiplies candidate weights by **fixed** per-model weights, merges duplicates, retains up to 12 candidates, and sorts them for coding. If the actual byte is not among those candidates, the arithmetic coder writes an escape and then the raw byte value uniformly. After coding or decoding, `WikiMix5Model::observe` updates the models and history.

The sequence is the same on decode: rebuild the candidate list from already restored bytes, decode either one of its candidates or the escape-plus-byte fallback, then update every model. A structural predictor can help near markup; a word predictor can help inside a repeated word; neither must be correct on every byte. The fallback keeps the combined model lossless even when all five miss.

That fallback is essential: a limited candidate list must never make an unseen byte impossible. The fixed mixer is also why the design note calls for future adaptive weighting; this implementation is a learning and experimentation point rather than a finished prize codec.

The fixed weights are `[14, 8, 5, 10, 6]` in the order shown in the table. As an isolated calculation, suppose the byte PPM model proposes `A` with raw weight `2` and the structure model proposes the same `A` with raw weight `3`. The combined weight for `A` would include `2 × 14 + 3 × 8 = 52`. If other models also propose `A`, their contributions are added. The mixer keeps only the twelve highest-weight distinct byte candidates, then sorts them by byte value so both sides assign the same arithmetic ranges. An escape with weight `32` remains available even if the correct byte is outside that list. These numbers explain `Mixer::combine`; they are not a prediction claimed for a particular Wikipedia passage.

```sh
make roundtrip CODEC=wikimix5 INPUT=data/sample.txt
```

The current source functions `WikiMix5Model::predict`, `encode_symbol`, and `decode_symbol` implement this behavior. The design note describes proposed changes, including adaptive weights; those are not claims about the present codec. Keeping the proposal separate from current code matters when interpreting a measurement.

**Next:** [How the methods fit together](../course/synthesis.md) compares the codec families before the source walkthroughs.
