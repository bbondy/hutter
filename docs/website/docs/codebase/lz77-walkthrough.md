---
title: Read the LZ77 codec
description: Follow literal and match tokens from the input loop into the archive and back out.
---

# Read the LZ77 codec

[`src/lz77.rs`](https://github.com/bbondy/hutter/blob/main/src/lz77.rs) is a short codec module to read before the predictors. It has no probability table or bit-level writer: the archive contains literal bytes and instructions to copy earlier output. Read [LZ77 and back-references](../algorithms/lz77.md) first if those instructions are new to you.

## 1. Follow a `lz77` command

`Codec::parse("lz77")` in [`src/codec.rs`](https://github.com/bbondy/hutter/blob/main/src/codec.rs) selects `Codec::Lz77`. `main.rs` opens the input and output files, and `Codec::compress` calls `lz77::compress`. On decompression, `decompress_auto` sees the first four archive bytes, `LZ77`, and calls `lz77::decompress`. The filename does not make this choice.

The two public functions are near the top of the module. Read them before `find_match`.

## 2. Read the encoder loop

`compress` loads the input into `data`, writes `LZ77` and the original length, and starts `index` at zero. Each iteration asks `find_match(&data, index)` for a distance and length. If at least three bytes match, it writes a match token and skips that many input bytes. Otherwise it writes one literal and advances one byte.

| Token | Bytes written | Decoder action |
| --- | --- | --- |
| Literal | tag `0`, then the byte | Append that byte. |
| Match | tag `1`, two-byte little-endian distance, one-byte length | Copy `length` bytes from `distance` bytes back. |

For `ABABABAB`, the encoder can write two literals (`A`, `B`) followed by a match with distance `2` and length `6`. The input is eight bytes; the archive still has a 12-byte header, so this small example is not a size win. Its purpose is to make the token meanings visible.

## 3. Read the match finder

`find_match` looks at candidate positions no more than 4 KiB behind the current `index`. For each candidate it measures how many next bytes match, up to 255. It keeps the longest match. A distance is `index - candidate`, not an absolute file position.

The comparison uses `length % distance`. This allows a match to overlap the bytes it is currently reproducing. After one `A` has been written, a match with distance `1` can produce a longer run of `A`s. The matcher is a direct scan of candidates, which is simple to follow but can be slow on large inputs.

## 4. Read the decoder and its checks

`decompress` reads the magic and original length, then reads one tag at a time until it has restored that many bytes. A literal appends one byte. For a match, it computes `start = restored.len() - distance`, then appends bytes from the earlier output. The modulo in its copy loop handles the same overlapping case as the encoder.

Before copying, it rejects distance `0`, a distance longer than the output so far, and match lengths below three. It also rejects unknown tags and any token that would make the restored output exceed the length in the header. An invalid archive should return an error rather than silently copying from an impossible position.

## 5. Tests in this module

```sh
cargo test lz77
make roundtrip CODEC=lz77 INPUT=data/sample.txt
```

`cargo test lz77` runs this module's tests. `roundtrip_repeated_text` checks repeated text; `roundtrip_binary` checks all byte values. The Makefile command checks the tracked sample. For a codec that gives individual values variable-length bit codes rather than copying runs, continue with the [block Huffman walkthrough](huffman-walkthrough.md).
