---
title: The competitive research track
description: Why the project studies a published compressor, how the prize score works, and what has actually been verified.
---

# The competitive research track

The Rust codecs in this course teach compression ideas and make small changes easy to test. The project also has a research track built around **cmix-neif 1.0**, a much more complex published Wikipedia compressor. That work lives on [`main`](https://github.com/bbondy/hutter/tree/main), alongside the original Rust lab. The repository keeps a pinned copy of the upstream source, so every local change can be compared with the same starting point.

The upstream implementation is a **candidate baseline**. Its reported score has not been reproduced by this project, and the Hutter Prize has not awarded it. See the [research workflow](https://github.com/bbondy/hutter/blob/main/engines/README.md) and check the [official prize site](https://prize.hutter1.net/) for the current record and rules.

## What counts as a prize result?

The prize uses the one billion byte `enwik9` corpus. A valid decoder must restore it exactly. The score includes the compressed archive **and** the executable and invocation material required by the rules; resource limits also matter. A 15 KB payload from a small fixture is useful research data, but it is not a prize score. A smaller development archive can lose overall if its executable grows more.

Our [selected upstream report](https://github.com/bbondy/hutter/blob/main/engines/cmix-neif/README.md) lists a 91,913,343-byte archive and a 4,000,689-byte executable, plus 19 bytes of invocation arguments: 95,914,051 bytes in that report. As checked October 17, 2026, the [official accepted record](https://prize.hutter1.net/) is 100,424,672 bytes. The reported candidate would be 4,510,621 bytes smaller **if** its full package and resource use qualify; it remains pending, not an awarded prize result. Those are upstream numbers, not a local full-corpus measurement. The project now reproduces the expected `comp9` binary hash with a native Ubuntu build, but still needs a measured full `enwik9` run and exact restoration on a persistent native Linux x86-64 machine.

A native Ubuntu hosted runner now reproduces the **exact published executable**
without Docker and passes the upstream packer/unpacker guards. The default host
had extra GCC 14 development files; after removing them, Clang selected GCC 13
and produced the original 4,000,689-byte compressor and its published SHA-256.
The [saved release evidence](https://github.com/bbondy/hutter/tree/main/benchmarks/weights/20261017-linux-packages-gcc13-v1)
records this control. Against that baseline, a weight permutation saves 8,563
bytes in measured release components while preserving both platforms' development
fixture archives. The complete release payload and full resource use remain
separate checks.

The [full-run harness](https://github.com/bbondy/hutter/tree/main/benchmarks/weights/20261017-full-release-protocol-v1)
is now prepared for a persistent Linux host. It pins both phases to one logical
CPU, decodes the SFX archive in a separate initially empty directory, checks
the full original hash and saves package sizes and resource samples. Disk
samples include open temporary files even after their directory entries are
deleted. A passing small harness test is not a full compression result; the
complete run has not yet happened. Resource sampling and directory separation
also do not replace the final judging procedure or enforce a sandbox.

Why not automatically adopt the smallest entry on a compression leaderboard? The [Large Text Compression Benchmark](https://mattmahoney.net/dc/text.html) ranks compressed size and lists `ex-girlfriend 1.0` ahead of cmix-neif as of its October 14, 2026 update. That benchmark does **not** award the Hutter Prize, and its timing and memory figures are approximate and may come from different machines. It reports about 10,204 MB and 220,071 ns per input byte for `ex-girlfriend`, versus 9,750 MB and 175,392 ns per byte for cmix-neif. The [prize task](https://prize.hutter1.net/) has roughly 10 GB and 50-hour limits on its own test machine. These numbers flag a real resource risk for either candidate; they cannot certify eligibility. The prize score also counts the submitted compressor, which the leaderboard's self-extracting archive column does not show as a separate cost. Measure the actual packaged submission on the target class of hardware before selecting a winner.

As checked October 18, the benchmark [explicitly labels Ex-Girlfriend 1.0 “not eligible”](https://www.mattmahoney.net/dc/text.html#ex-girlfriend), although it reports a verified 91,778,237-byte self-extracting archive, 135,106 bytes below cmix-neif's archive. Its [GPL-3.0 release source](https://github.com/rlanday/ex-girlfriend/tree/v1.0) is a derivative of the same cmix-neif revision. The author's [full-run record](https://github.com/rlanday/ex-girlfriend/blob/v1.0/README.md) reports about 61 hours to encode and 67 hours to decode on the measured host, with peak RSS close to 10 GiB. Those numbers do not establish that it can satisfy the [prize's machine-adjusted time and RAM rules](https://prize.hutter1.net/hrules.htm). We are keeping the exactly reproduced cmix-neif package as the control while assessing separately measured, low-overhead ideas from that GPL-3.0 derivative. Its page-id and timestamp forecasts deserve an isolated size, time and memory trial before its heavier online predictor or enlarged tables.

The [isolated E1 trial](https://github.com/bbondy/hutter/tree/main/benchmarks/metadata)
on native Mac fixtures saves **13 and 16 payload bytes** respectively; both
restore the original XML and keep baseline-identical context counters. Its
development executable grows 4,112 bytes before release packing. The two
payload gains do not establish a smaller scored package. The [native Linux
release check](https://github.com/bbondy/hutter/tree/main/benchmarks/metadata/20261023-e1-release-v1)
measures **2,094 additional bytes** across the packed compressor and
independent decoder prefix. Full-stream payload behavior remains unknown;
these small fixtures cannot pay for the measured package increase.
The [focused issue](https://github.com/bbondy/hutter/issues/18) tracks both
E1 and the separate timestamp forecast.

## Why keep two tracks?

The Rust lab gives a clear place to learn and test Huffman, LZ77, PPM and model mixing. The competitive candidate brings a larger predictor, transformer weights, text preprocessing, a dictionary and a self-extracting archive. Replacing the candidate with an educational Rust codec would require closing a very large measured gap before it could be a plausible prize entry.

The research tooling keeps the candidate's upstream source unchanged and applies Mac and comparison changes to disposable build copies. This lets experiments refer to one pinned baseline. The imported program declares GPL-3.0-only; the independent Rust lab and orchestration tools use the repository's MIT license. Read the [license scope](https://github.com/bbondy/hutter/blob/main/LICENSE-SCOPE.md) and upstream notices before distributing a derivative.

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
