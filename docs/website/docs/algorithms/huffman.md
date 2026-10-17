---
title: Huffman, two ways
description: Block-model and order-1 adaptive Huffman coding in the Rust source.
---

# Huffman, two ways

Before this page, read [prefix codes](../foundations/prefix-codes.md). A Huffman tree gives common byte values short bit paths and rare values longer paths. The tree is unambiguous because only leaves represent complete byte values.

## The default: `huffman`

The default codec lives in [`src/block_huffman.rs`](https://github.com/bbondy/hutter/blob/main/src/block_huffman.rs). It reads the input, writes an `AHF0` header, and processes blocks of at most 64 KiB. Both encoder and decoder begin with frequency `1` for every possible byte. For each block:

1. Build a Huffman tree from the **counts before this block**.
2. Encode or decode the complete block with that one tree.
3. Observe the decoded block’s bytes and update counts for the next block.

The first block therefore uses a tree built from equal initial counts. A later block can benefit from earlier blocks. The archive stores each block’s uncompressed length and encoded length, but it does not store a tree: the decoder reconstructs it from the same previous counts. Counts are rescaled when their sum grows too large.

For a small model-update illustration, pretend there are only four possible symbols. Begin with counts `A:1, B:1, C:1, D:1`, just as the real codec begins with one count for each possible byte. If the first block is `AAAA`, observing it changes the counts to `A:5, B:1, C:1, D:1`. A Huffman tree for the *second* block can now put `A` one edge from the root, while the rarer values have longer paths. The decoder rebuilds that second-block tree because it decoded the same first block and made the same count updates. The real model has 256 symbols and blocks of up to 64 KiB; the four-symbol table only makes the timing visible.

This matters for a tiny file. Even if its bytes are mostly `A`, the first block's tree was built *before* those `A`s were observed. The [prefix-code example](../foundations/prefix-codes.md) uses counts from its entire toy input to teach how a tree is made; the real first block cannot use those counts without storing them or sending the tree. A first-block archive can therefore be larger than the original. The benefit of observed counts appears in later blocks.

In fact, 256 equally weighted leaves make the first tree perfectly balanced, with an eight-bit code for every byte value. For any nonempty input that fits in a single block, its first payload therefore occupies the same number of bytes as the input. The archive also writes a 16-byte header and two four-byte block-length fields, making that archive **24 bytes larger** than the input. This is a property of this implementation's initial model and framing, not a general limit of Huffman coding.

```text
shared initial counts → block 1 tree → block 1 bytes → updated counts
updated counts       → block 2 tree → block 2 bytes → updated counts
```

## The contextual variant: `huffman-o1`

[`src/adaptive_huffman.rs`](https://github.com/bbondy/hutter/blob/main/src/adaptive_huffman.rs) uses `AHF1`. **Order 1** means the previous byte selects which frequency table and tree to use for the next byte. The previous-byte state starts at zero and continues across blocks. After coding each byte, this codec updates that context’s count and marks its tree for rebuilding. A “dirty” tree is rebuilt only when its context is next needed.

This can make `ABABAB` easier to model: after `A`, `B` becomes likely; after `B`, `A` becomes likely. It also does much more tree work than the block model, so the repo describes it as slower.

Here the update boundary is one **byte**, not one block. Before coding a byte, both sides choose a tree using the previous-byte context. After coding or decoding the byte, both sides update that context and advance the previous-byte state. The two formats use different magic bytes (`AHF0` and `AHF1`), so their archives are not interchangeable.

## What to look for in code

- `compress` writes the header and loops over blocks.
- `Model::new` establishes counts known to both sides.
- `build_tree` and `assign_codes` create the code paths.
- `BitWriter` and `BitReader` pack and unpack bits inside each block.
- The matching `decompress` performs model updates at the same boundaries.

The `make roundtrip` target accepts either `CODEC=huffman` or `CODEC=huffman-o1`. It checks exact restoration, not compression quality. A size comparison needs separate `ARCHIVE` paths because the default target path is otherwise reused. The [source walkthrough](../codebase/huffman-walkthrough.md) shows where both sides rebuild the default codec's tree.

**Next:** [LZ77](lz77.md), which describes repeated spans instead of assigning codes to values. To follow the default codec line by line, use the [block Huffman code walkthrough](../codebase/huffman-walkthrough.md).
