---
title: How the methods fit together
description: Compare what each codec represents, how its decoder recovers bytes, and why results differ.
---

# How the methods fit together

Every codec in this repository has the same lossless obligation: read input bytes, write an archive, and restore exactly those input bytes from the archive. They differ in **what they describe** and **how they code that description**. A shorter archive is useful only after exact restoration has been established.

## Three basic descriptions

| Description | The question it asks | What the decoder needs |
| --- | --- | --- |
| [Huffman](../algorithms/huffman.md) | Which individual byte values are common in the current model? | The same tree and the number of output bytes. |
| [LZ77](../algorithms/lz77.md) | Does a sequence of bytes repeat something already written? | Literal or match tokens and the earlier restored output. |
| [PPM](../algorithms/byte-ppm.md) | Given recent bytes or bits, what is likely next? | The same context counts, escape rules, arithmetic coder, and update order. |

`ABABABAB` shows the difference. A toy Huffman model built from the complete string sees four `A`s and four `B`s and can give each a short code. This repository's *first* Huffman block instead starts from uniform counts for all 256 byte values; it cannot use future counts. LZ77 can write `A`, `B`, then a backward match for the remaining six bytes. An order-1 byte PPM model gradually records that `B` follows `A` and `A` follows `B`; it uses those observations to change later probabilities. The three descriptions are not interchangeable archive formats, and none guarantees the smallest result for every file.

## Model and coder are different jobs

A **model** decides which outcomes are possible and how likely they are. A **coder** turns that decision into bits that a decoder can reverse. The block Huffman codec combines these jobs by building a prefix-code tree from counts, then writing the tree paths as bits. PPM variants supply symbol or bit probabilities to an arithmetic coder. LZ77 writes explicit tokens rather than coding a probability distribution in its own module.

The advanced codecs change the model, not the lossless contract:

| Family | Change to the prediction | Where it is explained |
| --- | --- | --- |
| [Bit PPM](../algorithms/bit-ppm.md) | Predict one bit at a time rather than one byte. | Bit histories and rebuilding bytes. |
| [PPMD](../algorithms/ppmd.md) | After an escape, exclude values that the longer context already ruled out. | Byte exclusion and bitwise forms. |
| [Mixing](../algorithms/mixing.md) | Combine several context predictions for the same next byte or bit. | Weights and byte-to-bit conversion. |
| [Match prediction](../algorithms/match.md) | Use a repeated sequence to predict a value rather than issuing a copy token. | Match-only and PPM-match formats. |
| [WikiMix-5](../algorithms/wikimix5.md) | Combine five byte predictors, including word and markup state. | Current fixed-weight implementation versus the design note. |

An arithmetic-coded model must leave a path for a value it has not predicted. Byte PPM uses escape and a final uniform byte choice; PPMD uses escape and an exclusion-aware fallback; mixed and match models retain their own fallback. A prediction can be wrong without corrupting the decoded file. It usually just costs more bits. Corruption happens when encoder and decoder disagree about a range, a format field, or the moment a model is updated.

## How this appears in an archive

The archive begins with a four-byte **magic** value, such as `AHF0`, `LZ77`, or `PP11`. [`decompress_auto`](https://github.com/bbondy/hutter/blob/main/src/codec.rs) uses that value to select the matching decoder. The chosen module then reads its own length fields and payload. The archive filename does not select the codec. The [archive-format chapter](../codebase/archive-format.md) lists the layouts and signatures.

This explains two common observations: a tiny input may grow because a header and payload framing still cost bytes, and a successful round trip does not by itself mean the archive is small or the codec is fast. The [experiments chapter](../contribute/experiments.md) separates correctness from size and runtime measurements.

**Next:** The [codebase overview](../codebase/overview.md) shows where these contracts are implemented. The [LZ77](../codebase/lz77-walkthrough.md), [Huffman](../codebase/huffman-walkthrough.md), and [byte PPM](../codebase/ppm-walkthrough.md) source walkthroughs follow them through real functions.
