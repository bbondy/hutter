# Hutter Prize

This repo is a workspace for experimenting toward a future Hutter Prize submission in Rust.

It is not competitive yet. The baseline compressor here is a simple adaptive block-Huffman coder whose only purpose is to give you a clean, testable loop for:

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

- `src/main.rs`: CLI
- `src/adaptive_huffman.rs`: baseline adaptive block-Huffman codec
- `data/sample.txt`: tiny sample corpus for smoke tests

## Commands

Build:

```sh
make build
```

Run a round-trip test on the sample file:

```sh
make roundtrip
```

Run the unit tests:

```sh
cargo test
```

Download the official `enwik9` corpus into `data/` if needed and verify it:

```sh
make enwik9
```

Run on a larger input:

```sh
make roundtrip INPUT=data/enwik9
make bench INPUT=data/enwik9
```

## Sources

- Official prize page: https://prize.hutter1.net/
- Official rules: https://prize.hutter1.net/hrules.htm
- Official FAQ: https://www.hutter1.net/prize/hfaq.htm
- 2024 winning repo: https://github.com/kaitz/fx2-cmix
- 2021 winning repo: https://github.com/amargaritov/starlit
