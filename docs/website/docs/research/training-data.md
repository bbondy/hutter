---
title: Inspect what the model actually sees
description: Reproduce training rows and check prompt coverage before changing a trained compressor.
---

# Inspect what the model actually sees

The transformer does not simply read raw Wikipedia XML. It sees a transformed
byte stream, dictionary codes, metadata prompts, retrieved link context and
alias rows. Some bytes are withheld from it. A proposed improvement must reach
the mechanism it is supposed to change: our first real-release prefix check
matched, but stopped in metadata while the transformer was disabled.

The upstream source includes a diagnostic mode that records this input sequence
without running transformer inference. Its match models and prompt automata
still run. Its constant predictions make the output unsuitable as a compressed
archive, but the recorded rows can be used to inspect coverage and construct
training data.

## Reproduce the data before changing it

The [frozen dump protocol](https://github.com/bbondy/hutter/tree/main/benchmarks/training)
starts with the already verified full coder-stream preparation. It copies the
recorded sources, checks their hashes and builds upstream's `TRAIN_MODE=2`.
The full dump must match the published 7,117,383,324-byte file and its SHA-256;
zone and match-channel files must also have the expected complete lengths.
The [native Mac reproduction](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-native-dump-v1)
now passes: the entire row dump matches SHA-256 `58fc6c74…f66a0`, and all three
zone/match files have the expected 552,750,204-byte lengths. The diagnostic
completed in about 40 minutes in this concurrent run; that is not compressor
runtime or a prize-resource result.

Each 12-byte record identifies a source position or an inserted row, a token,
previous tokens, a match feature and flags. Flags distinguish document starts,
redirects, metadata prompts, alias/author rows and whether the row's prediction
is masked from training targets. A streaming summary can count these without
loading the entire multi-gigabyte dump into memory.

The [verified full summary](https://github.com/bbondy/hutter/blob/main/benchmarks/training/20261017-native-coverage-v1/report.json)
counts the rows actually supplied to the model:

| Item | Count |
| --- | ---: |
| Data rows, excluding the header | 593,115,276 |
| Rows tied to coded-stream positions | 547,413,566 |
| Inserted rows | 45,701,710 |
| Unmasked rows | 547,585,952 |
| Metadata-prompt rows | 9,459,978 |
| Alias rows, excluding author bytes | 596,359 |
| Unmasked alias rows, excluding author bytes | 31,821 |
| Digit-run sentinel input rows | 7,153,276 |
| Model-document starts | 172,437 |

Categories overlap; they must not be added as if they were a partition.
Model documents are reset segments, not a count of raw XML pages. Stream
positions are strictly increasing, reserved fields are zero, and the final
position matches the full coded-stream length.

The first summary had an analysis bug: it confused the 208-symbol output
alphabet with the input vocabulary. Eight additional digit-run sentinel inputs
use tokens 208–215; they occur only in inserted rows. Previous-token fields also
use 216 as a reset marker. The
[failed analysis and diagnosis](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-coverage-analysis-failure-v1)
are retained. The corrected reader checks these roles and has a regression
test; the published-matching dump itself was never changed.

Coverage is different from value. Many retrieved tokens can hurt predictions;
an alias row that predicts a real byte can still be unhelpful to the final
mixture. The [link experiments](link-context.md) measure actual archives after
changing those mechanisms. A row count alone cannot replace that comparison.

## A bottleneck that tiny fixtures missed

The original diagnostic slowed sharply near 97% of the full stream. A
[three-second Mac profile](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-late-read-profile-v1)
found 238 of 252 sampled stacks in link-context history reads, mostly libc
seeks and reads. This is evidence about that short interval, not a measurement
of the whole run. Skipping transformer inference does not make every other
part of the pipeline cheap, and early progress cannot predict completion time.

A separate
[frozen diagnostic experiment](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-read-cache-protocol-v1)
uses a shared memory mapping for those history reads. It flushes pending writes,
checks that every requested byte is already observed, grows the mapping in
64 MiB steps and caps it at 1 GiB, with the original file-reader fallback above
that. The [completed cached run](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-read-cache-native-v1)
reproduces the published row dump and **all three original raster hashes**.
Independent verification checked the actual output files, binary, logs and
source inventory; only the two declared history-reader files changed.

| Diagnostic run | Wall time | Peak resident bytes |
| --- | ---: | ---: |
| Original file reader | 2,405.79 s | 4,636,557,312 |
| Mapped history reader | 810.75 s | 5,145,264,128 |

These concurrent single runs suggest a useful iteration improvement, but are
not a controlled speed comparison. The observed memory increase was about
509 MB. The patch changes only the training diagnostic: production archive
identity, release performance and prize-resource eligibility remain untested.
The original run and its evidence are retained separately.

## What a later training experiment would need

The first [pruning experiment](weight-pruning.md) removed neurons without
retraining and lost by a large margin. A smaller model might need better
selection, compensation or retraining. That would be a new experiment with a
frozen objective, recorded data, quantized export and full coder comparisons.
Teacher likelihood or training loss would be useful diagnostics, but the
archive and shipped model bytes remain the objective.

The row dump is only one part of the upstream training pipeline. Its PPMd prior
raster is roughly 228 GB, and its documented training chain uses multiple GPUs.
Neither the prior-generation run nor GPU training has been launched here.
Large generated data stays local; small reports, hashes, logs and failures go
into Git. Upstream trained on the target corpus, so this data does not create
an untouched validation set for our later model selection.
