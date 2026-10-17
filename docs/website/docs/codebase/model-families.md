---
title: Follow the other model families
description: Locate the prediction and update path in bit PPM, PPMD, mixed, match, and WikiMix codecs.
---

# Follow the other model families

The [byte PPM walkthrough](ppm-walkthrough.md) establishes a recurring order: derive a prediction from the old history, code or decode the next value, then update the model and history. The later codecs change the prediction, but not that order. This page identifies their entry points and the exact point where a complete byte becomes available.

## Bit PPM: one update per bit

[`src/ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm.rs) implements `ppm-bit` and its longer-order variants. `compress_with_order` uses `ByteBits` to turn each input byte into eight bits. For each bit, it calls `Model::encode_symbol`, `Model::observe`, then `BitHistory::push`. `decompress_with_order` does the matching `decode_symbol`, `observe`, and history push, while `ByteCollector` assembles output bytes.

`Model::encode_symbol` checks usable contexts from longest to shortest. A missing context is skipped. A present context that lacks the bit emits an escape. `context_is_usable` skips very long contexts until they have enough observations: orders up to 31 need at least one, orders 32–63 at least three, and order 64 at least five. That rule is shared by the decoder. The ordinary bit PPM loop does **not** wait for a full byte to update bit contexts.

## PPMD: exclusions during one symbol

[`src/ppmd.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd.rs) still codes whole bytes. `Model::encode_symbol` begins an `excluded` array with 256 `false` entries. It tries higher-order contexts first. After an escape, `Context::exclude_all` marks the symbols from that context. `Context::stats` and `Context::symbol_range` ignore excluded entries in the next context. If every context escapes, `encode_order_minus_one` gives each remaining byte one equal-frequency slot. The decoder rebuilds the same excluded array as it reads escapes; it never receives the array in the archive.

The exclusion array is new for *each byte being coded*. The learned context counts persist across bytes. After coding or decoding a byte, `Model::observe` updates counts using the old history, then the history advances.

## A byte predictor used for bits

[`src/ppmd_bit.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd_bit.rs) uses `BitModel::ensure_distribution` to build a distribution over 256 possible next bytes from PPMD-style contexts and their escapes. `bit_probability` sums the mass of bytes compatible with the bits already known in the current byte, separating those whose next bit is `0` from those whose next bit is `1`.

For a toy distribution with `0x41` weight three and `0xC3` weight one, the first bit is `0` with share `3/4`. If that bit is decoded as `0`, `0xC3` is no longer compatible with the current byte prefix. The actual model also includes fallback mass for bytes it has not seen. `observe_bit` collects bits into `current_byte`; only after eight bits does it update the byte contexts, push the completed byte into history, and invalidate the cached distribution. Updating the byte model after the first bit would let it learn a byte that has not yet been decoded.

## Mixers: several predictions, one coded outcome

[`src/hybrid_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/hybrid_ppm.rs) implements `ppm-mix`. `HybridModel::predictions` gathers bit-context and byte-context estimates for the **same next bit**. `HybridMixer::mixed_probability` combines them. `encode_bit` or `decode_bit` passes that one result to the arithmetic coder. `HybridModel::observe_bit` updates mixer weights and bit histories after the outcome; once eight bits are complete, it updates byte histories too. The weights are separate for each bit position within a byte.

Other mixes have different inputs: `ppm-byte-mix` uses several byte-context orders in `byte_ppm.rs`; `ppm-bit-mix` uses several bit-context orders in `ppm.rs`; `ppmd-mix` in `ppmd_mix.rs` combines direct bit contexts with a PPMD-derived byte distribution. The [mixing chapter](../algorithms/mixing.md) compares them without requiring their weight formulas on a first read.

## Matches and WikiMix

In [`src/ppm_match_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm_match_mix.rs), `MatchModel::observe` stores completed bytes and indexes recent four-byte suffixes. `refresh_candidates` checks earlier candidate positions and gives likely continuation bytes weights based on match length and distance. The standalone `match` codec's `MatchModel::encode_byte` either codes a predicted byte or writes an escape followed by a uniform byte value. `ppm-match-mix` instead contributes a match-based next-bit probability alongside byte-context predictions. These are different archive formats and loops in the same source file.

[`src/wikimix.rs`](https://github.com/bbondy/hutter/blob/main/src/wikimix.rs) codes whole bytes. `WikiMix5Model::predict` asks five models for candidate bytes; `Mixer::combine` applies fixed weights, merges duplicate byte candidates, and keeps at most twelve. `encode_symbol` or `decode_symbol` handles one candidate or an escape followed by a uniform byte. Only then does `WikiMix5Model::observe` update the predictors and history. Its [algorithm chapter](../algorithms/wikimix5.md) distinguishes this implemented fixed-weight mixer from the larger design note.

Across these modules, the safest source-reading question is: **which history and counts exist immediately before this value is coded?** The encoder and decoder must answer it identically. The [source map](map.md) lists every module; [archive formats](archive-format.md) explains how the dispatcher reaches them.
