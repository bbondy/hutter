---
title: Project and Hutter Prize
description: How the Rust lab and competitive research track relate to the Hutter Prize.
---

# Project and Hutter Prize

This repository has a Rust lab for testing lossless compression ideas and a [competitive research track](../research/competitive-baseline.md) on a separate branch. The lab contains several independent codecs, a command-line program to run them, a small sample input, and optional targets for downloading larger Wikipedia corpora. The research track studies a pinned published compressor. The project has not yet reproduced a full prize-valid score locally.

## The prize task

The [Hutter Prize](https://prize.hutter1.net/) uses `enwik9`, a file of exactly 1,000,000,000 bytes from Wikipedia. A valid result must reproduce those bytes exactly. The primary score is the combined size of the compressor and the self-extracting archive. The [official rules](https://prize.hutter1.net/hrules.htm) also describe allowed separate compressor and decompressor submissions, platform and resource limits, publication requirements, and the minimum improvement needed for an award.

The record and threshold change when a better submission is accepted. Check the [official prize page](https://prize.hutter1.net/) for the current value rather than relying on an old number in a checkout.

## What the Rust lab does now

The CLI has separate `compress` and `decompress` commands. That is convenient for experiments and round-trip tests, but it is not itself a self-extracting prize archive. `stats` reports the archive size and size of the running executable to help compare local results. Its total is a development measurement, not a claim that the output meets every prize rule.

The codecs cover [Huffman](../algorithms/huffman.md), [LZ77](../algorithms/lz77.md), [PPM](../algorithms/byte-ppm.md), [PPMD-style exclusion](../algorithms/ppmd.md), [mixed models](../algorithms/mixing.md), [match prediction](../algorithms/match.md), and [WikiMix-5](../algorithms/wikimix5.md). They are separate archive formats, selected by a four-byte signature during decompression. See the [codec reference](../reference/codecs.md) for every CLI name.

Many codecs read the complete input before coding, and the LZ77 matcher is deliberately simple. A successful round trip on the sample establishes correctness for that input; it does not establish competitive size, memory use, or runtime on `enwik9`.

## What the research track does now

The [`research/native-mac` branch](https://github.com/bbondy/hutter/tree/research/native-mac) vendors cmix-neif 1.0 as the candidate starting point. It contains a native Apple Silicon development port, a Linux comparison build, article-aware samples, and saved benchmark and parity records. The published upstream score and a matching reference binary hash are known; a local full `enwik9` result still needs verification. The [native/Linux case study](../research/native-parity.md) reports a small valid fixture and explains why almost equal archive sizes do not prove compatible bitstreams.

## What to do first

Use the tracked `data/sample.txt` and [run a Rust round trip](quickstart.md). Then read [what compression does](../foundations/what-is-compression.md). For Rust codec changes, follow the [experiments guide](../contribute/experiments.md); the larger corpora are optional. For prize research, start with the [competitive track](../research/competitive-baseline.md) and its [experiment playbook](../research/experiment-playbook.md).
