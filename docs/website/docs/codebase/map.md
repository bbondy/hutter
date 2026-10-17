---
title: Source map
description: Find the CLI, every codec family, helpers, tests, and optional data in the repository.
---

# Source map

For the directory tree and the relationship between these files, start with the [codebase overview](overview.md). This page is a lookup table. The project is a Rust **binary crate**: `Cargo.toml` names the executable package and `src/main.rs` declares its modules. Each codec module owns its model, coder, archive writing, decoding, and nearby tests. There is no separate library API to learn before reading a codec.

| File | Start here for |
| --- | --- |
| [`src/main.rs`](https://github.com/bbondy/hutter/blob/main/src/main.rs) | Command execution, file I/O, `stats`, and `profile`. |
| [`src/cli.rs`](https://github.com/bbondy/hutter/blob/main/src/cli.rs) | CLI syntax and argument parsing. |
| [`src/codec.rs`](https://github.com/bbondy/hutter/blob/main/src/codec.rs) | Codec names, aliases, compression dispatch, archive magic dispatch. |
| [`src/block_huffman.rs`](https://github.com/bbondy/hutter/blob/main/src/block_huffman.rs) | Default block Huffman and bit packing. |
| [`src/adaptive_huffman.rs`](https://github.com/bbondy/hutter/blob/main/src/adaptive_huffman.rs) | Previous-byte Huffman contexts and lazy tree rebuilding. |
| [`src/lz77.rs`](https://github.com/bbondy/hutter/blob/main/src/lz77.rs) | Literal and back-reference tokens. |
| [`src/byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs) | Byte PPM orders 1–6 and byte order mixing. |
| [`src/ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm.rs) | Bit PPM orders 8–64 and bit order mixing. |
| [`src/ppmd.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd.rs) | PPMD-style byte exclusion. |
| [`src/ppmd_bit.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd_bit.rs) | PPMD byte distribution converted to next-bit probabilities. |
| [`src/ppmd_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppmd_mix.rs) | PPMD byte predictions mixed with bit contexts. |
| [`src/hybrid_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/hybrid_ppm.rs) | `ppm-mix`: byte and bit predictors combined. |
| [`src/ppm_match_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm_match_mix.rs) | Hashed match prediction, `match`, `ppm-match-mix`, and profiling configurations. |
| [`src/wikimix.rs`](https://github.com/bbondy/hutter/blob/main/src/wikimix.rs) | Five-model wiki experiment. |
| [`src/io_utils.rs`](https://github.com/bbondy/hutter/blob/main/src/io_utils.rs), [`src/progress.rs`](https://github.com/bbondy/hutter/blob/main/src/progress.rs) | File and progress helpers. |

## Where tests and data live

Most modules end with a `#[cfg(test)]` section containing local round-trip and edge-case tests. `cargo test` runs them together. [`Makefile`](https://github.com/bbondy/hutter/blob/main/Makefile) provides build, roundtrip, bench, and optional corpus-download targets. `data/sample.txt` is tracked and small. The large `data/enwik8` and `data/enwik9` files are optional and ignored by Git.

[`docs/wikimix5.md`](https://github.com/bbondy/hutter/blob/main/docs/wikimix5.md) is a design note, not the current behavior contract. For exact codec behavior, read the Rust source and tests.

## A reading strategy

Open one codec’s `compress`, then its `decompress`. Read the two loops side by side before looking at optimized helpers. The [LZ77 walkthrough](lz77-walkthrough.md) starts with literal and match tokens. The [block Huffman walkthrough](huffman-walkthrough.md) adds trees and bit packing. The [byte PPM walkthrough](ppm-walkthrough.md) adds a model that predicts and updates after each byte.

**Next:** [The wire format](archive-format.md) and [contributor onboarding](../contribute/onboarding.md).
