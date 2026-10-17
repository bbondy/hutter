---
title: Codec reference
description: Every codec name, archive signature, model family, and Rust module.
---

# Codec reference

`compress` accepts `--codec NAME`; without it, the CLI uses `huffman`. `decompress` chooses a decoder from the archive header, so it takes no codec name. The table lists the primary names printed by [`Codec::name`](https://github.com/bbondy/hutter/blob/main/src/codec.rs); `Codec::parse` also accepts some aliases.

| CLI name | What it models or writes | Magic | Source |
| --- | --- | --- | --- |
| `huffman` | One byte Huffman tree per block, adapted between blocks | `AHF0` | `block_huffman.rs` |
| `huffman-o1` | Previous-byte Huffman contexts, adapted per byte | `AHF1` | `adaptive_huffman.rs` |
| `lz77` | Literal and back-reference tokens | `LZ77` | `lz77.rs` |
| `ppm-o1` | Byte PPM, max context 1 byte | `PP11` | `byte_ppm.rs` |
| `ppm-o2` | Byte PPM, max context 2 bytes | `PP12` | `byte_ppm.rs` |
| `ppm` | Byte PPM, max context 3 bytes | `PP13` | `byte_ppm.rs` |
| `ppm-o4` | Byte PPM, max context 4 bytes | `PP14` | `byte_ppm.rs` |
| `ppm-o5` | Byte PPM, max context 5 bytes | `PP15` | `byte_ppm.rs` |
| `ppm-o6` | Byte PPM, max context 6 bytes | `PP16` | `byte_ppm.rs` |
| `ppm-byte-mix` | Adaptive mix of byte PPM orders | `PPMX` | `byte_ppm.rs` |
| `ppm-bit` | Bit PPM, max context 8 bits | `PB08` | `ppm.rs` |
| `ppm-bit-o16` | Bit PPM, max context 16 bits | `PB16` | `ppm.rs` |
| `ppm-bit-o32` | Bit PPM, max context 32 bits | `PB32` | `ppm.rs` |
| `ppm-bit-o64` | Bit PPM, max context 64 bits | `PB64` | `ppm.rs` |
| `ppm-bit-mix` | Adaptive mix of bit PPM orders | `PBMX` | `ppm.rs` |
| `ppmd` | Exclusion-based byte PPMD-style model | `PPMD` | `ppmd.rs` |
| `ppmd-bit` | PPMD byte distribution converted to bit probabilities | `PDBT` | `ppmd_bit.rs` |
| `ppmd-mix` | PPMD byte and bit-history predictions mixed | `PDMX` | `ppmd_mix.rs` |
| `ppm-mix` | Byte and bit PPM predictions mixed | `PMIX` | `hybrid_ppm.rs` |
| `match` | Hashed next-byte match predictor | `PMAT` | `ppm_match_mix.rs` |
| `ppm-match-mix` | Byte PPM plus match predictor | `PMM3` | `ppm_match_mix.rs` |
| `wikimix5` | Five wiki-oriented next-byte predictors | `WMX5` | `wikimix.rs` |

`PMAT` and `PMM3` decoders also accept older payload forms (`PMAT` without the `MBY1` marker and `PMM2`, respectively). See [archive formats](../codebase/archive-format.md) for the wire layout and [source map](../codebase/map.md) for links to each file.

## Command shape

```sh
cargo run --release -- compress [--no-progress] [--codec NAME] INPUT ARCHIVE
cargo run --release -- decompress [--no-progress] ARCHIVE OUTPUT
cargo run --release -- stats [--no-progress] INPUT ARCHIVE
cargo run --release -- profile [--no-progress] INPUT
```

Square brackets here mean “optional”; do not type them literally. `profile` runs only the internal match-mix configurations. `--no-progress` is useful when saving command output or following a lesson.

For a first run, use [the quickstart](../start/quickstart.md).
