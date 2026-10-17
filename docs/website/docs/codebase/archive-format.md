---
title: Archive formats
description: What magic bytes and length fields the decoder reads before processing payloads.
---

# Archive formats

An **archive format** is the byte layout written by one codec. These formats are project experiments; they are not gzip, ZIP, or interoperable PPMd archives. The first four bytes are an ASCII **magic** signature. [`decompress_auto`](https://github.com/bbondy/hutter/blob/main/src/codec.rs) uses it to select a decoder.

## Common layouts

Most arithmetic-coded codecs use:

```text
4 bytes: magic | 8 bytes: original length (little-endian u64) | coded payload
```

`AHF0` and `AHF1` use:

```text
4 bytes: magic | 4 bytes: block size | 8 bytes: original length
repeat: 4 bytes uncompressed block length | 4 bytes payload length | payload
```

`LZ77` uses a 4-byte magic and 8-byte original length, then literal or match tokens. New `PMAT` match-only archives put `MBY1` between the length and the byte-oriented arithmetic payload. The `PMAT` decoder also recognizes older payloads without that marker.

**Little-endian** means the least significant byte of a multibyte integer comes first. The original length is not itself compressed. It lets the decoder stop after reconstructing exactly that many bytes.

The first bytes of three representative archives can be read by offset:

| Byte offsets | `AHF0` block Huffman | `LZ77` | `PP11` byte PPM |
| --- | --- | --- | --- |
| `0`–`3` | Four-byte magic `AHF0` | Four-byte magic `LZ77` | Four-byte magic `PP11` |
| `4`–`7` | Block size as a `u32` | First four bytes of original length | First four bytes of original length |
| `8`–`11` | First four bytes of original length | Last four bytes of original length | Last four bytes of original length |
| `12`–`15` | Last four bytes of original length | Literal or match tokens begin | Arithmetic payload begins |
| From `16` | Each block begins with two `u32` lengths, then its bit payload | More tokens | More arithmetic payload |

An offset is a zero-based position in the archive. `u32` is a four-byte unsigned integer and `u64` is an eight-byte unsigned integer. The default Huffman block size is 64 KiB, or 65,536 bytes; its little-endian header field is `00 00 01 00`. The [LZ77 worked example](../algorithms/lz77.md#a-complete-small-example) lists every archive byte for `ABABABAB`, including a distance stored as `02 00`.

## Magic signatures

| Signature | Decoder family |
| --- | --- |
| `AHF0`, `AHF1` | Default block Huffman; order-1 adaptive Huffman |
| `LZ77` | LZ77 token stream |
| `PP11`–`PP16` | Byte PPM orders 1–6 |
| `PPMX` | Mixed-order byte PPM |
| `PB08`, `PB16`, `PB32`, `PB64` | Bit PPM maximum orders 8, 16, 32, 64 |
| `PBMX` | Mixed-order bit PPM |
| `PPMD`, `PDBT`, `PDMX` | PPMD byte, PPMD-derived bit, PPMD and bit mix |
| `PMIX` | Combined byte and bit PPM (`ppm-mix`) |
| `PMAT` | Match-only, with legacy decode support |
| `PMM3`, `PMM2` | Current and legacy match mix |
| `WMX5` | WikiMix-5 |

## Inspect an archive

```sh
cargo run --release -- compress --no-progress --codec lz77 data/sample.txt build/sample.lz77
od -An -tx1 -N 16 build/sample.lz77
```

The first four hex bytes for `LZ77` are `4c 5a 37 37`. The next eight encode the input length. For another codec, change `--codec` and the output path; do not rely on the filename extension to identify it.

The magic and length fields are not a checksum. They identify the decoder and bound how much output it intends to produce, but they do not prove that the payload has not been changed. `decompress_auto` checks for at least four bytes before dispatch; each codec is responsible for validating the rest of its own format. Arithmetic bit readers may pad a short payload with zero bits, so not every damaged arithmetic archive is guaranteed to fail with an error. Exact round-trip tests and malformed-input tests answer different questions.

:::warning[When changing a format]
A new encoder layout needs a distinct magic or a deliberate version marker and matching decoder branch. Otherwise old archives may be interpreted with the new rules. Keep a round-trip test for new output and a fixture or test for any legacy format you intend to support.
:::

**Next:** [Codec names and formats](../reference/codecs.md).
