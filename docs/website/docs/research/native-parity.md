---
title: A native and Linux comparison
description: Two measured fixtures with matching initialization, diverging probabilities, and a reversed size gap.
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

## A second, disjoint sample

The team prepared 12 complete articles from the middle of `enwik8`, beginning at source offset 49,000,139. This gives 162,057 raw XML bytes and 154,286 bytes after the same upstream preprocessing. The inverse transform restored the raw selection before either build ran.

| Measurement | Apple Silicon Mac | Linux x86-64 in emulation |
| --- | ---: | ---: |
| Prepared input | 154,286 bytes | 154,286 bytes |
| Compressed payload | 21,149 bytes | 21,147 bytes |
| Coder events | 720,856 | 720,856 |
| Encode time in this run | 226.76 s | 1,083.93 s |

Initialization and every event type and input bit match again. This time, 405,844 integer probabilities differ; the first is at event 386, and payloads first differ at byte 50. The Linux payload is **two bytes smaller** than the Mac payload, reversing the first sample's one-byte Mac advantage. The [paired report](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/parity/20261017-middle-fixture-v1/report.json) and [event analysis](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/parity/20261017-middle-fixture-v1/trace-analysis.json) preserve the measurements.

Both decoders restored this prepared sample exactly and reproduced their respective encoders' initialization and full probability traces. The Linux self-decode took 1,044.36 seconds under emulation; its [validation record](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/parity/20261017-middle-linux-selfdecode-v1/report.json) is saved separately. This is same-platform validation for two different archives, not cross-platform decoding. Two different fixtures do not measure a model change, but the reversed size gap is direct evidence against assuming that Mac-only size gains will have the same sign on Linux.

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

## Full-corpus stages that do match

We can verify important parts of the pipeline without first running the full
adaptive compressor. The native Mac helper reproduced the pinned upstream
article order for all **243,425 pages**, including its census and comment-index
transforms. Its 998,030,918-byte main stream matches upstream's recorded digest.
The [ordering investigation](article-order.md) explains that check.

The native dictionary derivation also consumed the full verified billion-byte
enwik9 file and the pinned hints. It produced the **exact shipped 520,804-byte
dictionary**, with SHA-256
`0ab9f2d2733003577b53b206791f382fd31b91eff9975041b2173bb5585c5535`.
The [saved derivation record](https://github.com/bbondy/hutter/blob/main/benchmarks/pipeline/20261017-native-dictionary/report.json)
includes the input, source, compiler, executable and output hashes. The measured
run took 67.69 seconds with other jobs active.

The first combined Mac stream check **failed**: it produced 559,634,858
packed stream bytes instead of 552,750,198. The unpacked form was also
6,884,660 bytes larger. The [failed record](https://github.com/bbondy/hutter/tree/main/benchmarks/pipeline/20261017-native-stream-rejected)
remains saved. Native Linux then reproduced both upstream reference hashes
exactly, locating the difference after article ordering, in phda9 preprocessing.

The cause was two inherited XML entity operations that depended on **signed
integer overflow**. For example, the Mac helper left `&lt;sup&gt;` where Linux
reduced it to `<sup>`. Both could reverse their own representation correctly,
so a round trip alone did not expose the compatibility problem. An overflow
sanitizer catches the original arithmetic. Replacing those two expressions with
explicit unsigned arithmetic fixes the discrepancy without changing global
model compiler flags.

The corrected Mac tool now matches the native Linux tool and both full upstream
stream references:

| Preparation output | Bytes | Mac and Linux |
| --- | ---: | --- |
| Before metadata packing | 555,771,398 | Exact upstream SHA-256 |
| Packed coder stream | 552,750,198 | Exact upstream SHA-256 |

The [Linux record](https://github.com/bbondy/hutter/blob/main/benchmarks/pipeline/20261017-linux-stream-v1/report.json)
and [corrected Mac record](https://github.com/bbondy/hutter/blob/main/benchmarks/pipeline/20261017-native-stream-v3/report.json)
retain stage hashes, source inventories and commands. These are the bytes fed to
the coder, **not compressed archives**. The integer preprocessing fix does not
establish agreement between adaptive floating-point predictions or a full prize
score. Earlier Mac fixture results use the old entity representation; new
comparisons require regenerated prepared inputs and fresh baselines.

## What to do with this result

Use the Mac build to explore ideas quickly. Check any promising size change on Linux before treating it as progress toward the prize. Neither of these two small samples establishes that candidates will rank the same on both systems. Full `enwik9` score, runtime, memory and packaging remain separate gates.

**Next:** [Plan comparable experiments](experiment-playbook.md).
