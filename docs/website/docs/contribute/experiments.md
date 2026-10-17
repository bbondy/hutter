---
title: Experiments and measurement
description: Compare codecs without losing correctness, and understand what the project measures.
---

# Experiments and measurement

Compression research has two separate questions: **does it restore the exact bytes?** and **does it improve a useful metric?** Check correctness first. A smaller archive is meaningless if it changes the data.

## A simple experiment loop

```sh
make roundtrip INPUT=data/sample.txt CODEC=ppm ARCHIVE=build/sample.ppm RESTORED=build/sample.restored
make bench INPUT=data/sample.txt CODEC=ppm ARCHIVE=build/sample.ppm
```

`roundtrip` builds, compresses, decompresses, and calls `cmp`. `bench` compresses and runs `stats`; it reports size, not a timing benchmark. For a direct timing comparison, use a tool such as your shell’s `time` command and run several times after a warm-up. The `profile` subcommand measures internal `ppm-match-mix` configurations on one input and reports their time and archive sizes.

Keep the input, compiler mode (`--release`), machine, and archive paths consistent when comparing versions. Tiny samples are good for debugging but are dominated by headers. Keep both input and archive for a comparison rather than overwriting one codec’s result with another.

## Optional corpora

`make enwik8` downloads and checksum-verifies the 100 MB corpus; `make enwik9` does the same for the 1 GB corpus. `make corpora` requests both. These files are ignored by Git. Start with `data/sample.txt`, then use `enwik8` only when a change survives the small tests. Consult the [Makefile](https://github.com/bbondy/hutter/blob/main/Makefile) for the download URLs and expected SHA-1 values.

## What `stats` means

`stats` prints the archive size and the size of the **currently running executable**, then calls their sum `total S`. The Hutter Prize judges a compressor plus archive, so archive bytes alone are not the whole target. This CLI is still an experiment harness with separate compress/decompress commands; its `stats` output is a local comparison aid, not a prize-valid submission measurement. A release build and a debug build have very different executable sizes.

For example, consider two hypothetical runs on the same input. Codec A makes a 600-byte archive with a 180,000-byte executable: its reported total is 180,600 bytes. Codec B makes a slightly smaller 590-byte archive but requires a 200,000-byte executable: its total is 200,590 bytes. Archive size alone favors B; this particular combined-size measure favors A. The real executable contains the whole CLI, not a separately packaged decoder for each format, so these figures illustrate the arithmetic of `stats`, not a prize score.

## Keep an experiment reproducible

Record the codec name, Git revision, input checksum, archive size, executable size, runtime, and whether a round trip passed. For predictor changes, note how memory use changes on larger inputs. If a result looks dramatic, rerun it and inspect the resulting archive header and restored bytes. The [archive guide](../codebase/archive-format.md) and [source map](../codebase/map.md) help locate surprising behavior.

**Next:** [Review the complete codec list](../reference/codecs.md).
