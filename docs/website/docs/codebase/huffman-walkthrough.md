---
title: Read the block Huffman codec
description: Follow the default codec's header, block loop, tree reconstruction, bit I/O, and tests.
---

# Read the block Huffman codec

This page follows the actual `huffman` implementation in [`src/block_huffman.rs`](https://github.com/bbondy/hutter/blob/main/src/block_huffman.rs). If a tree or prefix code is unfamiliar, read [prefix codes](../foundations/prefix-codes.md) first. The [Rust notation page](rust-primer.md) explains `Result`, `?`, slices, and generic readers.

## 1. Find the entry point

This command compresses the tracked sample from the repository root:

```sh
mkdir -p build
cargo run --release -- compress --no-progress --codec huffman data/sample.txt build/sample.huf
```

In `src/cli.rs`, `parse_args` selects `Codec::BlockHuffman`. `main.rs` opens the files and calls `codec.compress(...)`. The `BlockHuffman` arm in [`Codec::compress`](https://github.com/bbondy/hutter/blob/main/src/codec.rs) calls `block_huffman::compress`.

You can stop at that function for a first read. The command-line parser and progress wrapper do not change the compressed data.

## 2. Read the header and one block

At the top of `compress`, `read_to_end` loads the input bytes. The next three writes make the archive header:

| Write in `compress` | Bytes | Why the decoder needs it |
| --- | --- | --- |
| `MAGIC`, which is `AHF0` | 4 | Select this decoder. |
| `DEFAULT_BLOCK_SIZE` | 4 | Limit the size of each decoded block. |
| `data.len()` | 8 | Know the total number of original bytes to restore. |

The integers are written little-endian. The codec then creates `Model::new()`, whose 256 frequency counts all start at `1`. That initial state is fixed in the source, not stored in the archive.

The block loop does four things in order:

```text
build_codes(current counts)
encode_block(input block, codes)
write block length, payload length, and payload
model.observe(input block)
```

A block is at most 64 KiB. `build_codes` runs **before** `model.observe`, so the current block uses counts from earlier blocks only. The first block uses the equal starting counts. The next block uses counts updated with the first block's bytes. This differs from the [small interactive Huffman example](../lab.mdx), which builds a tree from its whole input.

## 3. Find the bits

`build_tree` creates a leaf for every byte value and repeatedly joins the two lowest-frequency nodes. A **heap** is a container that can return a lowest-weight item efficiently. The code uses one with a defined tie order, so encoder and decoder build the same tree when counts are equal. `assign_codes` walks left with `0` and right with `1` to produce a `Code { bits, len }` for each byte.

`encode_block` looks up each input byte's code and passes it to `BitWriter`. `BitWriter::write_bits` fills output bytes one bit at a time. `finish` pads the last output byte if necessary; that padding is not an extra decoded symbol, because the archive records how many original bytes belong to the block.

You do not need to understand the heap implementation to check the important relationship: **the tree depends only on counts both sides already know**. No tree is serialized for each block.

## 4. Read the decoder beside the encoder

[`block_huffman::decompress`](https://github.com/bbondy/hutter/blob/main/src/block_huffman.rs) first checks `AHF0` and reads the header. It creates the same initial model. For each block it reads the two lengths and payload, builds a tree from the current counts, and calls `decode_block` to recover exactly `block_len` bytes. `BitReader` supplies one bit at a time; `decode_block` follows left or right until it reaches a leaf, which gives one byte.

Only after writing the restored block does the decoder call `model.observe(&block)`. The encoder and decoder therefore update counts at the same boundary:

```text
encoder: tree from old counts → encode block → observe block
decoder: tree from old counts → decode block → observe block
```

If one side updates before building the tree, the next block uses different codes and cannot decode correctly. The decoder also rejects an invalid block size, impossible block lengths, and a payload that ends before enough symbols have been decoded.

## 5. Tests in this module

At the end of `src/block_huffman.rs`, `roundtrip_small_text` and `roundtrip_binary` compress bytes into a `Vec`, decompress them, and compare the restored bytes with the input. This command runs just that module's tests:

```sh
cargo test block_huffman
```

For a second codec with a visibly different archive body, compare [LZ77 and back-references](../algorithms/lz77.md). For a codec whose model changes after each byte rather than each block, read the [byte PPM walkthrough](ppm-walkthrough.md).
