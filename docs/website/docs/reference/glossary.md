---
title: Glossary
description: Plain-language definitions for the terms used throughout the compression guide.
---

# Glossary

**Archive** — The compressed file produced by a codec. It includes format information as well as coded data.

**Arithmetic coder** — A way to turn a sequence of probability-based decisions into a compact bitstream by narrowing a numerical interval.

**Back-reference** — An instruction to copy bytes from an earlier part of the already decoded output. Used by [LZ77](../algorithms/lz77.md).

**Bit** — A value of `0` or `1`. Eight bits form a byte.

**Binary** — Base-two notation, using only `0` and `1`; each digit of a byte is one bit.

**Byte** — A number from `0` to `255`, represented by eight bits. Files in this project are byte sequences.

**Codec** — An encoder and its matching decoder, plus the archive format they agree on.

**Decoder** — The program logic that reads an archive and reconstructs the original bytes.

**Context** — Already-seen bytes or bits used to predict the next value. An order-3 byte context is the previous three bytes.

**Entropy** — Average ideal coding cost for a known probability distribution. It is a reference point, not the size of an actual archive.

**Escape** — A coded signal that the current model or context did not supply the actual value; the decoder should try a fallback.

**Exclusion** — Removing values seen at a longer context from the choices at a shorter context after an escape. Used by this repo’s [PPMD-style codec](../algorithms/ppmd.md).

**Frequency** — A count of how many times a symbol followed a particular context or appeared in a block. Counts are used to estimate probabilities.

**Header** — The initial archive fields that identify a format and carry information such as the original length.

**Hexadecimal** — Base-sixteen notation for bytes, using digits `0`–`9` and letters `A`–`F`. `0x41` is the same byte value as decimal `65`.

**Huffman code** — A prefix-free variable-length code derived from symbol frequencies.

**KiB** — A kibibyte, equal to 1,024 bytes. A 4 KiB window holds up to 4,096 bytes.

**Literal** — A byte written directly rather than as a copy from earlier data.

**Little-endian** — Storing the least significant byte of a multibyte integer first; the number two as a two-byte value is `02 00`.

**Lossless** — Decompression restores every original byte exactly.

**Magic** — A recognizable header signature at the start of an archive; the CLI uses its first four bytes to select a decoder.

**Mixer** — A model that combines several next-byte or next-bit predictions into one probability distribution.

**Model** — The state and rules used to predict the next byte or bit. Encoder and decoder maintain matching model states.

**Order** — How much recent history a context includes. Check whether the particular codec counts bytes or bits.

**Probability** — A number from `0` to `1` assigned to an outcome; larger values mean the model expects that outcome more strongly.

**Renormalization** — Expanding a narrowed integer coding range after settled leading bits have been emitted, so more symbols can be coded with finite precision.

**Payload** — The encoded data after a format’s header and length fields.

**PPM** — Prediction by partial matching: try a long context, then shorter contexts if needed.

**Prefix-free** — No complete codeword is the start of another codeword, so a decoder can split a bitstream unambiguously.

**Round trip** — Compress, decompress, then verify that the output is byte-for-byte identical to the input.

**Symbol** — One value coded by a model; in this project it is often a byte, sometimes a bit, and sometimes an escape event.

**UTF-8** — A common text encoding in which a written character may occupy one or more bytes.

**Window** — The earlier portion of input or output in which an LZ or match model searches for repeated data.

Return to [the reading path](../start/reading-path.md) or [the interactive examples](../lab.mdx).
