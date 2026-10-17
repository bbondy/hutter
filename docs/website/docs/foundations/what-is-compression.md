---
title: What compression does
description: Lossless reconstruction, redundancy, archive overhead, and the encoder-decoder contract.
---

# What compression does

A file is an ordered sequence of **bytes**. A byte is a number from `0` to `255`; the next chapter explains how those numbers represent text and other data. **Lossless compression** turns the file into an archive that a decoder can use to recover *exactly* the original bytes.

```text
original bytes → compressor → archive bytes → decompressor → identical original bytes
```

“Identical” includes spaces, line endings, and bytes that do not display as text. If even one byte changes, the round trip has failed. This differs from lossy image or audio compression, which may discard information to reduce size.

## A description both sides understand

Consider `AAAAAA`. A possible description is “the byte `A`, repeated six times.” That description is useful only if the decoder knows where the byte and count are stored and how to distinguish this instruction from other instructions. For `banana banana`, a description could instead point backward to an earlier run of bytes. For text with a common byte such as `e`, a code could give that byte a shorter bit pattern.

These are three ways to use **redundancy**: a repeated value, a repeated sequence, or an uneven distribution of values. The description itself must be unambiguous. The Rust codecs use different archive formats, but each encoder and its decoder agree on the format in advance.

An archive usually has a **header** and a **payload**. The header identifies the format and often records the original length. The payload carries the coded values or instructions. For example, this project's `LZ77` archive starts with four bytes spelling `LZ77` and eight bytes recording the original length; tokens follow. These first four bytes are called the format's **magic**. The extension of the archive filename is not used to choose a decoder.

## Why some files grow

A description has a cost. A one-byte file still needs an archive header, so this project's codecs can produce an archive larger than that input. A match token may be longer than the bytes it replaces. A model can predict badly. Compression is useful when savings from patterns exceed the cost of describing them.

No lossless scheme can shorten *every* possible input. To see why, fix a length such as two bytes: there are `256 × 256` distinct two-byte files, but fewer distinct byte strings of lengths zero or one. Two different inputs cannot share the same archive if the decoder must recover each exactly. There simply are not enough shorter outputs for all inputs.

## How the decoder gets the same model

A **model** is a rule for representing or predicting data. Some formats store the needed instructions explicitly. `lz77` stores literal bytes and backward-copy tokens. Other formats use **shared adaptation**: the encoder and decoder begin with the same initial counts, then change those counts after each decoded block, byte, or bit. Because the decoder has reconstructed the same data so far, it can make the same next prediction without receiving the whole model in the archive.

This gives a central rule for the project: both sides must update their state at the same point. If the encoder updates before coding a value and the decoder updates after decoding it, their next predictions disagree. The original length in the header also tells a decoder when to stop, even if the final payload byte contains unused bits.

The repository explores these methods for the [Hutter Prize](https://prize.hutter1.net/), a lossless Wikipedia compression challenge. Its CLI is an experiment program, not yet a prize submission. The [project page](../start/project.md) explains that context without requiring it for the compression lessons.

**Next:** [Bytes and bits](bytes-and-bits.md) explains exactly what a codec reads and writes.
