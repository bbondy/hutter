---
title: Plan and keep compression experiments
description: Choose valid samples, compare changes fairly, and save the evidence needed to judge a prize candidate.
---

# Plan and keep compression experiments

For a small model change, ask two questions: **does the decoder still restore the original bytes?** and **does the change reduce the measured size on the target build?** A single smaller Mac payload is a lead; the Linux and full-corpus measurements decide whether it helps the prize entry.

## Use samples that exercise the real pipeline

The competitive candidate expects its own text preprocessing and metadata. An arbitrary byte slice from `enwik8` is not a valid dictionary-mode input. The research tooling selects complete Wikipedia articles, applies the upstream `phda9` transform and verifies that the inverse restores the selected raw bytes. A manifest records source offsets, article count, hashes and transform details. The 19-article fixture has 117,161 raw bytes and 108,927 prepared bytes. A larger 172-article fixture has also passed preprocessing and inverse checks, but has not yet been compressed in the recorded comparison.

Tiny samples help catch correctness problems. They are poor throughput tests for this engine because dictionary pretraining costs roughly 145 seconds per native encoding even on the small fixture. Use a small valid fixture for screening, then a larger and a held-out fixture before promoting a result. The research branch also prepares a disjoint middle-of-`enwik8` fixture with the same article-aware transform; its manifest records where extraction actually began. Change one model idea at a time and keep the baseline binary and input fixed for each paired comparison.

## Save enough to reproduce a result

For every run, retain the input hash and preprocessing manifest, binary hash, source revision and patch, compiler and flags, dictionary and weight hashes, exact command, payload bytes, encode/decode times, peak memory and round-trip outcome. Save failed trials too: a mismatch is evidence about where a change stopped working. The research branch has [benchmark history](https://github.com/bbondy/hutter/blob/research/native-mac/benchmarks/README.md) for codec trials and a separate [parity harness](https://github.com/bbondy/hutter/blob/research/native-mac/engines/ports/cmix-neif-parity/README.md) for cross-platform checks. Large trace streams stay local; reports and hashes are committed to Git.

The saved parity reports are readable as a small table:

```bash
python3 scripts/parity_history.py list
python3 scripts/parity_history.py compare BEFORE AFTER
```

`list` includes completed paired encodings, with their source offset, article count, prepared size, both payload sizes and byte-equality status. `compare` reports byte deltas only when the prepared input, page count, assets, reference image and upstream source match. A different fixture is a **generalization check**, not a fair before/after score for a model change. Decoder-only and diagnostic records remain available by record ID, but do not appear as compressed-size results.

| Gate | Promote when… |
| --- | --- |
| Preprocessing | The inverse restores every raw input byte. |
| Local encoding | The decoder restores the prepared input and a repeat produces the same archive. |
| Linux comparison | The same candidate improves on the same prepared input with the same assets and manifest. |
| Full prize run | Packaged bytes, exact `enwik9` restoration, runtime and peak memory all meet the current rules. |

For performance claims, run several comparable trials on an idle machine. Do not compare an emulated Linux time with a native Mac time as a hardware benchmark. Prize scoring needs the archive and required executable and arguments, not just the payload shown by a local fixture test.

## Current next moves

1. Finish the Linux development decoder's own round-trip check and keep the result with the existing encoder record.
2. Measure more than one article-aware fixture on both platforms to see whether model changes rank consistently.
3. Reproduce the pinned submission's full `enwik9` result and packaged size on native Linux x86-64, with exact restoration and resource measurements.
4. Evaluate one promising predictor change against that frozen baseline. Investigate exact ARM floating-point parity where it changes a real decision; keep Linux as the scoring reference meanwhile.

The [native/Linux comparison](native-parity.md) explains why those gates are separate. The [Rust experiments guide](../contribute/experiments.md) remains useful for learning codecs and testing their own archive formats.

There are two tempting dead ends. Shrinking a fixture to a few bytes does not remove dictionary pretraining, so it barely speeds up an experiment. Making every Apple Silicon floating-point calculation identical to the x86 build could be a large project; begin with the measured first difference and spend that effort only when it improves the research loop. The current candidate also has upstream [attribution and licensing questions](https://github.com/bbondy/hutter/blob/research/native-mac/engines/cmix-neif/training/ATTRIBUTION.md#7-open-points) that need review before distributing a derived submission.
