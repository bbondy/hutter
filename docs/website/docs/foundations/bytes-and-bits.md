---
title: Bytes and bits
description: The exact units compressed by this project, with text encoding and bit order explained.
---

# Bytes and bits

A **bit** is one choice between `0` and `1`. Eight bits make a **byte**. Since each bit has two choices, eight bits give `2 × 2 × 2 × 2 × 2 × 2 × 2 × 2 = 256` possible byte values, numbered `0` through `255`.

## Reading one byte in three number systems

The byte `01000001` has eight **binary** digits. From left to right, their place values are `128, 64, 32, 16, 8, 4, 2, 1`. Only the `64` and `1` places are set, so this byte is `65` in ordinary decimal notation.

Hexadecimal is a shorter way to write the same value. One hexadecimal digit represents four bits. `0100` is `4`; `0001` is `1`; together they are `0x41`. The `0x` prefix means “the following digits are hexadecimal,” not that the byte changed.

| View | The same one-byte value |
| --- | --- |
| Bits | `01000001` |
| Decimal | `65` |
| Hexadecimal | `0x41` |
| Text under ASCII or UTF-8 | `A` |

Text needs an **encoding**, a rule that maps characters to bytes. Under UTF-8, `A` occupies one byte (`0x41`), but `é` occupies two (`0xC3 0xA9`). A file containing `é` is therefore not a one-byte file. The compressor works on bytes, not visible letters; it also works on binary data that is not text. A byte-for-byte comparison is the right correctness check.

This is what a hexadecimal dump shows on macOS or Linux:

```text
printf 'A' | od -An -tx1    → 41
printf 'é' | od -An -tx1    → c3 a9
```

`od` displays the bytes; `-tx1` asks for one-byte hexadecimal values. An **offset** is a byte's position in a file, starting at zero. The first four bytes at offsets `0` through `3` often identify an archive format. They are still ordinary bytes, even when they spell letters such as `LZ77`.

## Byte models and bit models

A **byte model** chooses among up to 256 possible next bytes. A **bit model** chooses between `0` and `1` eight times to reconstruct a byte. The CLI name `ppm-o3` uses a context of up to three previous **bytes**; `ppm-bit-o32` uses up to 32 previous **bits**. A context is simply the recent data used to make a prediction.

The bit-oriented codecs in this repository process each byte from its leftmost, most-significant bit to its rightmost bit. For `0x41`, that order is `0, 1, 0, 0, 0, 0, 0, 1`. The decoder collects eight bits in that same order to rebuild `0x41`. Neither unit is automatically better: byte models make one larger choice, while bit models make eight smaller choices.

**Next:** [Probability and surprise](probability.md) explains why common or predictable values can cost fewer bits.
