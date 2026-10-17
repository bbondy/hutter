---
title: Codebase overview
description: Where the Rust program starts, how codec modules fit together, and which file to open for a change.
---

# Codebase overview

This section is for reading or changing the Rust program. It is separate from the [compression foundations](../foundations/what-is-compression.md): you can learn the algorithms without reading Rust. If you do want to work on the code, begin here and then follow one archive through its encoder and decoder.

## Repository layout

```text
hutter/
├── Cargo.toml          Rust package and edition
├── Cargo.lock          locked Rust dependency versions
├── Makefile            build, round-trip, benchmark, and corpus commands
├── src/
│   ├── main.rs         program entry point and file handling
│   ├── cli.rs          command-line argument parsing
│   ├── codec.rs        codec names, compression dispatch, archive detection
│   ├── block_huffman.rs, lz77.rs, byte_ppm.rs, ...
│   │                   individual compression formats
│   ├── io_utils.rs     file-reading helpers
│   └── progress.rs     progress reporting
├── data/sample.txt     small input for experiments
└── docs/
    ├── wikimix5.md     WikiMix design note
    └── website/         this tutorial and its GitHub Pages build
```

This is one Rust **binary crate**: Cargo builds a command-line program, not a reusable library. `src/main.rs` declares the modules. Most codec modules contain both `compress` and `decompress`, their model or token logic, their archive layout, and tests. There is no single compressor class that every codec inherits from.

The optional `data/enwik8` and `data/enwik9` corpora are not needed to read or test the code. Cargo creates `target/` when it builds; the Makefile writes example archives into `build/`. Neither directory is source code.

## How the files work together

```text
compress: CLI text → cli.rs → main.rs → codec.rs → selected codec module → archive
decompress: archive → main.rs → codec.rs reads its first four bytes → codec module → original bytes
```

`cli.rs` turns command-line text into a `Command`. `main.rs` opens files and executes that command. `codec.rs` maps a chosen `Codec` value to an encoder. On decompression, it checks the archive's **magic** bytes to select a decoder; the filename extension is not used. The selected module owns the remaining format and the algorithm.

For the exact call path, read [follow one file through the code](flow.md). For a list of every codec module, use the [source map](map.md).

## Choose a reading path

| If you want to… | Open… |
| --- | --- |
| Understand the program before editing it | [Rust notation used here](rust-primer.md), then [follow one file](flow.md) |
| See a short encoder and decoder with explanations | [LZ77 walkthrough](lz77-walkthrough.md) |
| See trees and bit packing in the default codec | [Block Huffman walkthrough](huffman-walkthrough.md) |
| Understand a predictor and arithmetic coder | [Byte PPM walkthrough](ppm-walkthrough.md), after [byte PPM concepts](../algorithms/byte-ppm.md) |
| Follow the integer coder in detail | [The integer arithmetic coder](arithmetic-coder.md) |
| Locate later predictors and their update timing | [Other model families](model-families.md) |
| Find a particular format or test | [Source map](map.md) and [codec reference](../reference/codecs.md) |
| Change an archive header | [Archive formats](archive-format.md) and the codec's `compress`/`decompress` functions |
| Make a change and check it | [Developer onboarding](../contribute/onboarding.md) |

When reading a codec, find its public `compress` and `decompress` functions first. Follow the data from the header into one block, token, byte, or bit. Then look at the helper that builds a code or prediction. You do not need to understand the optimized models before you can follow the file path.
