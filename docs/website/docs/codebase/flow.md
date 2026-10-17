---
title: Follow one file through the code
description: Trace compress and decompress from command line to synchronized model updates.
---

# Follow one file through the code

Knowing an algorithm is different from knowing where its bytes move. Trace a small `huffman` archive first, then compare a PPM archive.

## Compression path

```text
terminal arguments
  → cli::parse_args
  → main::run opens the input and output files
  → Codec::compress selects a module
  → module::compress writes header and encoded payload
```

In [`src/cli.rs`](https://github.com/bbondy/hutter/blob/main/src/cli.rs), `parse_args` turns strings into a `Command`. If `--codec` is absent, `compress` chooses `huffman`. In [`src/main.rs`](https://github.com/bbondy/hutter/blob/main/src/main.rs), `run` opens files and wraps the input reader with progress reporting. In [`src/codec.rs`](https://github.com/bbondy/hutter/blob/main/src/codec.rs), `Codec::compress` maps the chosen variant to a module function.

For `huffman`, [`block_huffman::compress`](https://github.com/bbondy/hutter/blob/main/src/block_huffman.rs) reads the input, writes `AHF0`, a block size, and the original byte length. It builds one tree per block from the prior counts, writes each block’s lengths and bit-packed payload, then observes the block for the next tree.

## Decompression path

```text
archive file
  → main::run reads archive bytes
  → codec::decompress_auto checks first four bytes
  → matching module::decompress validates header
  → model restores original bytes to output file
```

The decompressor does not use the archive filename or extension. `decompress_auto` checks the **magic** (the first four bytes) and invokes the corresponding decoder. That decoder parses the rest of its own format. The original length tells it when to stop; for Huffman, each block also carries an output length and payload length.

## The shared-model invariant

For a PPM codec, both sides execute a loop like this:

```text
encoder: predict → encode actual symbol → observe actual symbol → advance history
decoder: predict → decode symbol        → observe decoded symbol → advance history
```

Before a symbol, each side has seen the same prefix, so its prediction and arithmetic ranges must match. This is why [`byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs) calls `model.observe` *after* `encode_symbol`, and the decoder calls it *after* `decode_symbol`. If you change this order in one direction only, the first affected symbol will desynchronize the archive.

## Files that are easy to miss

`src/io_utils.rs` reads archive data with progress and obtains file lengths. `src/progress.rs` implements the progress wrapper; `--no-progress` makes teaching examples and scripted measurements easier to read. `src/main.rs` also implements `stats` and `profile`; those commands do not change an archive.

**Next:** [Read the block Huffman codec](huffman-walkthrough.md), then use the [source map](map.md) for another module.
