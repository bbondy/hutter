---
title: Your first round trip
description: Build the Rust CLI, compress a small file, decompress it, and verify every byte.
---

# Your first round trip

A **round trip** means compressing a file, decompressing the archive, and checking that the result is byte-for-byte identical to the original. This is the first test for any lossless codec.

## What you need

- [Rust and Cargo](https://www.rust-lang.org/tools/install). Rust is the programming language; `cargo` is its build and run tool.
- A **terminal**, an application where you type commands, opened in the repository root. The root is the folder containing `Cargo.toml` and `src/`. If you do not have a checkout, `git clone https://github.com/bbondy/hutter.git` downloads one, and `cd hutter` enters it.
- `cmp` for the manual comparison below. It is available on macOS and most Linux systems; `cargo test` works on platforms without it.

No Wikipedia download is needed. The repository includes `data/sample.txt`.

## Build and run

```sh
cargo build --release
mkdir -p build
cargo run --release -- compress --no-progress --codec huffman data/sample.txt build/sample.huf
cargo run --release -- decompress --no-progress build/sample.huf build/sample.restored
cmp data/sample.txt build/sample.restored
```

`cmp` prints nothing and exits successfully when the files match. The first `cargo run` may compile the program again only if the source changed. You can also run `make roundtrip`, which builds, runs both commands, and calls `cmp` for you.

In these commands, `--release` asks Cargo for an optimized build. The first `--` separates Cargo's options from the program's options. `--codec huffman` chooses the compressor; `--no-progress` suppresses progress messages so output is easier to read. `mkdir -p build` creates the output folder if it does not exist. The last two paths of `compress` are the input and archive; those of `decompress` are the archive and restored output.

The archive extension `.huf` is only a convenient label. The decoder chooses a codec by the first four bytes of the archive, so it does not need `--codec` on `decompress`.

## The same process with LZ77

```sh
cargo run --release -- compress --no-progress --codec lz77 data/sample.txt build/sample.lz77
cargo run --release -- decompress --no-progress build/sample.lz77 build/sample.restored
cmp data/sample.txt build/sample.restored
cargo run --release -- stats --no-progress data/sample.txt build/sample.lz77
```

The `stats` command prints the input size, archive size, size of the current executable, and their combined size. A tiny file may **grow** after compression because its archive header and tokens cost space. That is normal and useful to notice.

:::note[Makefile shorthand]
`make roundtrip CODEC=ppm INPUT=data/sample.txt` performs the same compress, decompress, and byte-comparison steps for byte PPM. The larger Wikipedia files are not needed for these commands.
:::

## What just happened?

```text
sample.txt --read bytes--> codec --write archive--> sample.huf
sample.huf --read header--> matching decoder --write bytes--> sample.restored
```

The CLI argument parser lives in [`src/cli.rs`](https://github.com/bbondy/hutter/blob/main/src/cli.rs); the dispatch table is [`src/codec.rs`](https://github.com/bbondy/hutter/blob/main/src/codec.rs). We trace that path in [one file through the code](../codebase/flow.md).

**Next:** [Probability and surprise](../foundations/probability.md) explains why different bytes can need different numbers of bits. The [interactive examples](../lab.mdx) show three simplified representations.
