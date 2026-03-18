# Hutter Prize

This repo is a workspace for experimenting toward a future Hutter Prize submission in Rust.

It is not competitive yet. The current repo contains three small experimental codecs:

- adaptive block Huffman
- order-1 adaptive block Huffman
- naive LZ77 with literal and back-reference tokens
- bit-level PPM with arithmetic coding

There is also an additive `WikiMix-5` design skeleton for a future mixed-model codec:

- `src/wikimix.rs`
- `docs/wikimix5.md`

Codec names in the CLI:

- `huffman`: original block-model Huffman codec, faster and the default
- `huffman-o1`: order-1 Huffman codec, usually slower
- `lz77`: naive LZ77 codec
- `ppm-bit`: order-3 bit-level PPM-style arithmetic coder
- `ppm-bit-mix`: mixed-order bit-level PPM candidates with adaptive per-order weights

Their purpose is to give you a clean, testable loop for:

- compress
- decompress
- verify correctness
- inspect file sizes quickly

## Current target

As of the latest official record on the Hutter Prize site, the enwik9 record to beat is:

- `110,793,128` total bytes by Kaido Orav and Byron Knoll with `fx2-cmix` on September 3, 2024

For a prize-eligible submission, you need at least a 1% improvement over the previous record, which means:

- your total `S = compressor + archive` must be below `109,685,197` bytes

Recent enwik9 records listed by the official site:

- `110,793,128` bytes, `fx2-cmix`, Kaido Orav and Byron Knoll, September 3, 2024
- `112,578,322` bytes, `fx-cmix`, Kaido Orav, February 2, 2024
- `114,156,155` bytes, `fast cmix`, Saurabh Kumar, July 16, 2023
- `115,352,938` bytes, `starlit`, Artemiy Margaritov, May 31, 2021
- `116,673,681` bytes, `phda9v1.8`, Alexander Rhatushnyak, July 4, 2019

## What the contest actually requires

The official task is to create a Linux or Windows compressor plus a self-extracting archive that reproduces `enwik9` exactly, with these practical constraints:

- lossless reconstruction of the exact `enwik9`
- total size counts both the compressor executable and the produced archive
- the archive must be self-contained, so yes, you effectively need decompression support
- documented source code must be published under an OSI-approved license before prize payment
- practical limits are roughly single-core, under 10 GB RAM, and under about 50 hours on the prize machine

For this starter repo, the CLI uses separate `compress` and `decompress` commands because that is easier to iterate on. Later, if you approach a serious submission, you would likely switch to a self-extracting archive flow.

## Language notes

Recent winning submissions are mostly C++-centric `cmix` derivatives with shell scripts and, in some cases, Python or notebooks for preprocessing.
Rust is not the common language in public Hutter Prize winners, but it is still a reasonable choice for a clean experimental codebase.

## Workspace layout

- `src/main.rs`: top-level entrypoint
- `src/cli.rs`: command-line parsing and usage text
- `src/codec.rs`: codec selection and archive-format dispatch
- `src/block_huffman.rs`: original adaptive block-Huffman codec
- `src/adaptive_huffman.rs`: slower order-1 adaptive block-Huffman codec
- `src/lz77.rs`: simple LZ77 codec
- `src/ppm.rs`: bit-level PPM-style arithmetic codec
- `data/sample.txt`: tiny sample corpus for smoke tests
- `data/enwik8`: optional 100 MB Hutter corpus for faster iteration
- `data/enwik9`: optional 1 GB Hutter Prize corpus for full-scale benchmarking

## Commands

Build:

```sh
make build
```

Run a round-trip test on the sample file:

```sh
make roundtrip
```

Select a codec explicitly:

```sh
make roundtrip CODEC=huffman
make roundtrip CODEC=huffman-o1
make roundtrip CODEC=lz77
make roundtrip CODEC=ppm-bit
make roundtrip CODEC=ppm-bit-mix
make roundtrip CODEC=wikimix5
```

Run a round-trip with an explicit codec:

```sh
cargo run --release -- compress --codec huffman data/sample.txt build/sample.huf
cargo run --release -- decompress build/sample.huf build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec huffman-o1 data/sample.txt build/sample-o1.huf
cargo run --release -- decompress build/sample-o1.huf build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec lz77 data/sample.txt build/sample.lz77
cargo run --release -- decompress build/sample.lz77 build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-bit data/sample.txt build/sample.ppm
cargo run --release -- decompress build/sample.ppm build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-bit-mix data/sample.txt build/sample.pmix
cargo run --release -- decompress build/sample.pmix build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec wikimix5 data/sample.txt build/sample.wmx5
cargo run --release -- decompress build/sample.wmx5 build/sample.restored
cmp data/sample.txt build/sample.restored
```

If `--codec` is omitted, `compress` defaults to `huffman`. `decompress` auto-detects the archive format from the file header, so you do not need to specify the codec when restoring.

Run the unit tests:

```sh
cargo test
```

Download the official Hutter corpora into `data/` and verify them:

```sh
make enwik8
make enwik9
make corpora
```

`make corpora` downloads and verifies both `enwik8` and `enwik9`. `make data-files` is an alias for the same target.

Run on a larger input:

```sh
make roundtrip INPUT=data/enwik8
make bench INPUT=data/enwik8
make bench INPUT=data/enwik8 CODEC=huffman
make bench INPUT=data/enwik8 CODEC=huffman-o1
make bench INPUT=data/enwik8 CODEC=ppm-bit
make bench INPUT=data/enwik8 CODEC=ppm-bit-mix
make bench INPUT=data/enwik8 CODEC=wikimix5
make roundtrip INPUT=data/enwik8 CODEC=huffman ARCHIVE=build/enwik8.ahf1 RESTORED=build/enwik8.ahf1.restored
make roundtrip INPUT=data/enwik8 CODEC=huffman-o1 ARCHIVE=build/enwik8.ahf1 RESTORED=build/enwik8.ahf1.restored
make roundtrip INPUT=data/enwik8 CODEC=lz77 ARCHIVE=build/enwik8.lz77 RESTORED=build/enwik8.lz77.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-bit ARCHIVE=build/enwik8.ppm RESTORED=build/enwik8.ppm.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-bit-mix ARCHIVE=build/enwik8.pmix RESTORED=build/enwik8.pmix.restored
make roundtrip INPUT=data/enwik8 CODEC=wikimix5 ARCHIVE=build/enwik8.wmx5 RESTORED=build/enwik8.wmx5.restored

make roundtrip INPUT=data/enwik9
make bench INPUT=data/enwik9
make bench INPUT=data/enwik9 CODEC=huffman
make bench INPUT=data/enwik9 CODEC=huffman-o1
make bench INPUT=data/enwik9 CODEC=ppm-bit
make bench INPUT=data/enwik9 CODEC=ppm-bit-mix
make bench INPUT=data/enwik9 CODEC=wikimix5
make roundtrip INPUT=data/enwik9 CODEC=huffman ARCHIVE=build/enwik9.ahf1 RESTORED=build/enwik9.ahf1.restored
make roundtrip INPUT=data/enwik9 CODEC=huffman-o1 ARCHIVE=build/enwik9.ahf1 RESTORED=build/enwik9.ahf1.restored
make roundtrip INPUT=data/enwik9 CODEC=lz77 ARCHIVE=build/enwik9.lz77 RESTORED=build/enwik9.lz77.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-bit ARCHIVE=build/enwik9.ppm RESTORED=build/enwik9.ppm.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-bit-mix ARCHIVE=build/enwik9.pmix RESTORED=build/enwik9.pmix.restored
make roundtrip INPUT=data/enwik9 CODEC=wikimix5 ARCHIVE=build/enwik9.wmx5 RESTORED=build/enwik9.wmx5.restored
```

## Sources

- Official prize page: https://prize.hutter1.net/
- Official rules: https://prize.hutter1.net/hrules.htm
- Official FAQ: https://www.hutter1.net/prize/hfaq.htm
- 2024 winning repo: https://github.com/kaitz/fx2-cmix
- 2021 winning repo: https://github.com/amargaritov/starlit
