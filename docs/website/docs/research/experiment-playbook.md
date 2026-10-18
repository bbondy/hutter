---
title: Plan and keep compression experiments
description: Choose valid samples, compare changes fairly, and save the evidence needed to judge a prize candidate.
---

# Plan and keep compression experiments

For a small model change, ask two questions: **does the decoder still restore the original bytes?** and **does the change reduce the measured size on the target build?** A single smaller Mac payload is a lead; the Linux and full-corpus measurements decide whether it helps the prize entry.

## Use samples that exercise the real pipeline

The competitive candidate expects its own text preprocessing and metadata. An arbitrary byte slice from `enwik8` is not a valid dictionary-mode input. The research tooling selects complete Wikipedia articles, applies the upstream `phda9` transform and verifies that the inverse restores the selected raw bytes. A manifest records source offsets, article count, hashes and transform details. The current screening set has 172 pages and 1,033,597 raw bytes; a disjoint set has 138 pages and 1,005,977 raw bytes. Both include redirect and main-text phases.

There are two separate preprocessing requirements: restore every original byte, and produce the representation used by the reference build. An inherited signed-overflow expression produced different XML entity encodings on Mac and Linux while both could still restore their own inputs. The [portability correction](native-parity.md) now reproduces both full upstream coder-stream hashes on both platforms. Fresh frozen fixtures keep the same raw pages and permutations while using those corrected entity encodings. Earlier tables remain available with their older representation clearly labeled.

Tiny samples help catch correctness problems. They are poor throughput tests for this engine because dictionary pretraining costs roughly 145 seconds per native encoding even on the small fixture. Use a small valid fixture for screening, then a larger and a held-out fixture before promoting a result. The repository also measured a disjoint middle-of-`enwik8` fixture with the same article-aware transform; its manifest records where extraction actually began. Its Mac/Linux size gap reversed direction from the first fixture. Change one model idea at a time and keep the baseline binary and input fixed for each paired comparison.

## Save enough to reproduce a result

For every run, retain the input hash and preprocessing manifest, binary hash, source revision and patch, compiler and flags, dictionary and weight hashes, exact command, payload bytes, encode/decode times, peak memory and round-trip outcome. Save failed trials too: a mismatch is evidence about where a change stopped working. The repository has [benchmark history](https://github.com/bbondy/hutter/blob/main/benchmarks/README.md) for codec trials and a separate [parity harness](https://github.com/bbondy/hutter/blob/main/engines/ports/cmix-neif-parity/README.md) for cross-platform checks. Large trace streams stay local; reports and hashes are committed to Git.

The saved parity reports are readable as a small table:

```bash
python3 scripts/parity_history.py list
python3 scripts/parity_history.py decoders
python3 scripts/parity_history.py compare BEFORE AFTER
```

`list` includes completed paired encodings, with their source offset, article count, prepared size, both payload sizes and byte-equality status. `decoders` separately shows which same-platform archives restored exactly and reproduced their encoder traces. `compare` reports byte deltas only when the prepared input, page count, assets, reference image and upstream source match. A different fixture is a **generalization check**, not a fair before/after score for a model change. Decoder-only and diagnostic records remain available by record ID, but do not appear as compressed-size results.

| Gate | Promote when… |
| --- | --- |
| Preprocessing | The inverse restores every raw input byte, and prepared hashes match the reference representation. |
| Local encoding | The decoder restores the prepared input and a repeat produces the same archive. |
| Linux comparison | The same candidate improves on the same prepared input with the same assets and manifest. |
| Full prize run | Packaged bytes, exact `enwik9` restoration, runtime and peak memory all meet the current rules. |

For performance claims, run several comparable trials on an idle machine. Do not compare an emulated Linux time with a native Mac time as a hardware benchmark. Prize scoring needs the archive and required executable and arguments, not just the payload shown by a local fixture test.

## Current next moves

The [cycle-inspired article-order experiment](article-order.md) adds a concrete
example: the old 19-page fixture has no internal exact-title links, so testing
link-guided ordering requires the larger article set. It also exposes an inherited
redirect-block boundary. New fixture builds parameterize it and keep redirects
in a fixed prefix, with identical phase settings on the encoder and decoder.
The corrected screen and disjoint comparisons now pass exact original-byte
restoration and actual context-counter checks. A telemetry-disabled encoding
produces the identical baseline archive. Preserve legacy results separately:
a protocol change is a new baseline, not a model gain.

1. Keep the upstream ordering and link-context settings. The completed canonical [order comparisons](article-order.md) reject both proposed orders; the [link-context tests](link-context.md) reject all three reduced-context settings on both Mac and Linux. The older entity-representation results remain separate.
2. Continue paired comparisons on native Ubuntu x86-64 for new model hypotheses. The [manual CI workflow](https://github.com/bbondy/hutter/actions/workflows/linux-benchmarks.yml) rebuilds the frozen inputs, rejects hash mismatches, runs all choices serially per fixture and retains failures. Save its reports in Git before temporary artifacts expire. Local concurrent timings are exploratory.
3. The [exact-target filter](link-context.md) improved both reused Mac fixtures by 5 and 2 bytes, but native Linux saves 3 on the screen and loses 5 on the disjoint input. It fails Linux promotion. The frozen third-range trials also disagree by platform: Mac loses 5 bytes; Linux saves 2. All six outcomes are retained, and the original rule stays. This third range is now examined evidence for later tuning; upstream weights were also trained on the target corpus.
4. Reproduce the pinned submission's full `enwik9` result and packaged size on native Linux x86-64, with exact restoration and resource measurements. Dictionary derivation, upstream ordering, both full coder-stream hashes and the exact native Linux release executable now pass. Full compression and its resource limits remain unverified. Standard hosted CI has a six-hour job limit, so it cannot establish the much longer full reference run; that needs a persistent machine.
5. Keep the upstream depth setting: both [adaptive-depth candidates](adaptive-depth.md) lose on both native Linux fixtures. Continue [model-neuron permutation](weight-permutations.md) verification: it preserves both native Linux fixture archives and saves 8,563 bytes in measured release components against the reproduced published executable. A bounded full-input prefix comparison is running; full-corpus behavior and the complete prize score remain unverified.
6. Reject all three tested [pruning candidates](weight-pruning.md): they restore exactly, but their fixture payload penalties exceed their gross model-saving budgets by roughly 49–76 times. Future smaller-model work needs a different approach, such as activation-aware selection or retraining. The [complete training-row dump](training-data.md) now matches the published 7.1 GB hash; its prompt coverage is recorded, and MLP activity instrumentation preserves both archives: all 12,218 neurons activate, while the old 5% removals can include about 17% of a layer’s squared activation mass. Investigate exact ARM floating-point parity where it changes a research decision; use Linux as the scoring reference meanwhile.
7. Keep the original alias callback: the [prediction-refresh screen](link-context.md) adds 4 bytes on one Mac fixture and ties on the other, with identical context feed counts and exact restoration. It fails its predeclared promotion rule. The separate MLP activity probe is diagnostic only and must preserve the original archive.
8. Continue the fixed [CPU-trained bit predictor](bit-predictor.md): its Mac archives save 148 and 91 bytes, and native Linux saves 136 and 93 bytes on the screen and disjoint fixtures. All restore exact XML with matching context counts. The packed Linux release components also shrink 32 bytes against the exactly reproduced published baseline. The model and archive comparison protocols were frozen before their respective holdout checks. This is a small reused-fixture result; measure a longer stream and the full archive before treating it as a prize candidate.

The [native/Linux comparison](native-parity.md) explains why those gates are separate. The [Rust experiments guide](../contribute/experiments.md) remains useful for learning codecs and testing their own archive formats.

There are two tempting dead ends. Shrinking a fixture to a few bytes does not remove dictionary pretraining, so it barely speeds up an experiment. Making every Apple Silicon floating-point calculation identical to the x86 build could be a large project; begin with the measured first difference and spend that effort only when it improves the research loop. The current candidate also has upstream [attribution and licensing questions](https://github.com/bbondy/hutter/blob/main/engines/cmix-neif/training/ATTRIBUTION.md#7-open-points) that need review before distributing a derived submission.
