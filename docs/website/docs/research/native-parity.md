---
title: A native and Linux comparison
description: A measured example of matching initialization, diverging probabilities, and nearly equal archive sizes.
---

# A native and Linux comparison

A compressor driven by adaptive predictions has to make the same decisions during encoding and decoding. If it uses slightly different probabilities, its arithmetic coder can produce different bytes even when both programs read the same input. This is especially easy to overlook when moving a predictor from x86-64 Linux to Apple Silicon.

The project built a native Mac development version of the pinned cmix-neif candidate. It retains the predictor, transformer and weights. Its Linux comparison build retains the original x86 kernels and paging. Both builds add an explicit page count so they can read the same **prepared** 19-article sample rather than pretending a raw fragment is the full `enwik9` corpus. The sample starts as 117,161 bytes of original XML and becomes 108,927 bytes after the upstream `phda9` preprocessing. Both sides load the same dictionary and transformer weights.

## The result

| Measurement | Apple Silicon Mac | Linux x86-64 in emulation |
| --- | ---: | ---: |
| Prepared input | 108,927 bytes | 108,927 bytes |
| Compressed payload | 15,221 bytes | 15,222 bytes |
| Coder events | 473,488 | 473,488 |
| Encode time in this run | 195.61 s | 817.36 s |

The one-byte size gap is interesting, but the payloads are **different streams**. Every recorded event type and input bit matches; 272,752 of the final integer probabilities differ. The first probability difference is at event 190: 27,039 on Mac versus 27,029 on Linux while both code a zero bit. The payloads first differ at byte 29. An archive from one platform has not been shown to decode on the other.

These times are exploratory single runs with concurrent activity. In particular, Linux ran under x86 emulation on an ARM host. They are not a prize runtime comparison. Payloads here exclude the dictionary, weights and executable. The native build round-tripped the prepared sample and reversed preprocessing to restore all 117,161 original XML bytes. Tracing enabled and disabled yielded the same native payload hash.

The Linux development build also decoded **its own** 15,222-byte archive. It restored the 108,927 prepared bytes exactly, with initialization and the full probability trace matching its encoder. That emulated decode took 796.66 wall seconds. This closes a same-platform correctness check; it does not show that Linux can decode the different Mac payload. The [decoder validation record](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/parity/20261017-linux-selfdecode-v1/report.json) contains the result.

## What matched, and what did not?

The original Mac build used Darwin's `rand()` sequence; Linux uses a different one. An explicit generator was added to the Mac port. It matches 10,000 consecutive Linux draws for each of five seeds, including the entry's seed 923. The captured randomized LSTM weights and indirect-map offsets then matched byte for byte: 20,621,872 snapshot bytes with the same SHA-256 on both systems.

That check covered specific randomized arrays, **not every derived floating-point value**. A bounded diagnostic found a model input difference already at event 0: `-5.96046448e-8` on Mac versus `0` on Linux. The input comes from a neutral logit term; Mac fast-math code uses a rounded reciprocal and fused operation in its calculation. LSTM values differ by event 8, mixer outputs by event 10, and the final quantized coder probability differs by event 190. Fixing that first calculation has not been tested and may not resolve the later differences.

```text
same prepared bytes and random draws
        ↓
matching captured random weights and offsets
        ↓
different derived model input at event 0
        ↓
different internal predictions
        ↓
different coder probability at event 190
        ↓
different payload, despite almost equal size
```

The test harness saves binary hashes, source inventories, input hashes, traces and failed comparisons so this result can be checked later. The full [benchmark report](https://github.com/bbondy/hutter/blob/research/native-mac/docs/benchmarks/2026-10-17/native-parity.md), [probability comparison](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/parity/20261017-probabilities-v1/report.json), and [stage analysis](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/parity/20261017-numerical-prefix-v1/stage-analysis.json) contain the measurements and precise hashes.

## What to do with this result

Use the Mac build to explore ideas quickly. Check any promising size change on Linux before treating it as progress toward the prize. The one-byte size gap on one small sample does not establish that candidates will rank the same on both systems. Full `enwik9` score, runtime, memory and packaging remain separate gates.

**Next:** [Plan comparable experiments](experiment-playbook.md).
