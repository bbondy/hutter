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
This reproduction is running; no matching dump result is claimed yet.

Each 12-byte record identifies a source position or an inserted row, a token,
previous tokens, a match feature and flags. Flags distinguish document starts,
redirects, metadata prompts, alias/author rows and whether the row's prediction
is masked from training targets. A streaming summary can count these without
loading the entire multi-gigabyte dump into memory.

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
that. The complete row dump must still match the published reference. This
adds possible resident memory and changes only the diagnostic build. It is not
a production speed improvement or prize-memory claim; the original run and
its outcome are retained separately.

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
