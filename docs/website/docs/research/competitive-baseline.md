---
title: The competitive research track
description: Why the project studies a published compressor, how the prize score works, and what has actually been verified.
---

# The competitive research track

The Rust codecs in this course teach compression ideas and make small changes easy to test. The project also has a research track built around **cmix-neif 1.0**, a much more complex published Wikipedia compressor. That work currently lives on the [`research/native-mac` branch](https://github.com/bbondy/hutter/tree/research/native-mac), alongside the original Rust lab. The branch keeps a pinned copy of the upstream source, so every local change can be compared with the same starting point.

The upstream implementation is a **candidate baseline**. Its reported score has not been reproduced by this project, and the Hutter Prize has not awarded it. See the [research workflow](https://github.com/bbondy/hutter/blob/research/native-mac/engines/README.md) and check the [official prize site](https://prize.hutter1.net/) for the current record and rules.

## What counts as a prize result?

The prize uses the one billion byte `enwik9` corpus. A valid decoder must restore it exactly. The score includes the compressed archive **and** the executable and invocation material required by the rules; resource limits also matter. A 15 KB payload from a small fixture is useful research data, but it is not a prize score. A smaller development archive can lose overall if its executable grows more.

Our selected upstream report lists a 91,913,343-byte archive and a 4,000,689-byte executable, plus 19 bytes of invocation arguments: 95,914,051 bytes in that report. Those are upstream numbers, not a local full-corpus measurement. The project verified that its Linux reference image contains the expected `comp9` binary hash, but still needs a measured full `enwik9` run and exact restoration on a suitable native Linux x86-64 machine.

## Why keep two tracks?

The Rust lab gives a clear place to learn and test Huffman, LZ77, PPM and model mixing. The competitive candidate brings a larger predictor, transformer weights, text preprocessing, a dictionary and a self-extracting archive. Replacing the candidate with an educational Rust codec would require closing a very large measured gap before it could be a plausible prize entry.

The research branch keeps the candidate's upstream source unchanged and applies Mac and comparison changes to disposable build copies. This lets experiments refer to one pinned baseline. The imported program declares GPL-3.0-only; the independent Rust lab and orchestration tools use the repository's MIT license. Read the [license scope](https://github.com/bbondy/hutter/blob/research/native-mac/LICENSE-SCOPE.md) and upstream notices before distributing a derivative.

## What each development environment tells us

| Environment | Useful for | Limit |
| --- | --- | --- |
| Native Apple Silicon Mac build | Faster local model experiments without Docker | Its numerical predictions currently differ from the x86 Linux build. |
| x86-64 Linux build in an emulated container on the Mac | Checking the candidate's Linux behavior and archive size with the original x86 kernels | Emulation time cannot establish runtime eligibility. |
| Native Linux x86-64 machine | Full corpus, packaged submission, time and memory validation | A passing run still needs comparison with the current official record. |

The Mac port is a real development tool. The container is a useful Linux correctness and size check. Neither environment replaces the final native Linux measurement.

## A ladder of evidence

| Check | What it can establish | What it cannot establish |
| --- | --- | --- |
| Small prepared fixture restores exactly | This encoder and decoder agree on those bytes | A full-corpus score or resource compliance |
| Same fixture on Mac and Linux | Whether a change travels between the two builds | That the binaries produce identical streams on other inputs |
| Held-out, larger fixtures | Whether a candidate's size gain generalizes | Prize eligibility |
| Full `enwik9` run with packaged artifact | Actual size, exact restoration, runtime and memory for that build | Future wins against a moving record |

The [native/Linux case study](native-parity.md) shows why the second row is necessary. The [experiment playbook](experiment-playbook.md) explains how to save comparable results and decide when to move to the next row.

**Next:** [See what the native/Linux comparison found](native-parity.md).
