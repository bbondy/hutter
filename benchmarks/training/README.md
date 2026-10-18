# Training-data and prompt diagnostics

This directory holds both training-data diagnostics and the later bit-predictor
experiments. The upstream transformer-row dump skips inference and emits
constant predictions; it is not a valid compressed archive. Its matching hash
establishes data reproduction, while the separately linked archive records
measure actual coding changes.

The first [frozen protocol](20261017-dump-protocol-v1/protocol.json) reproduces
the full published 7,117,383,324-byte row dump from the already verified full
preparation build. The wrapper copies its recorded source files, checks every
hash, builds with `TRAIN_MODE=2`, and compares the output with the published
upstream SHA-256. It requires 15 GiB free and leaves large outputs local.

```sh
python3 scripts/training_dump.py \
  --stream-build build/native-stream-v3-entities \
  --protocol benchmarks/training/20261017-dump-protocol-v1/protocol.json \
  --output build/training-dump-native-v1
```

On native Linux use a matching successful Linux `native_stream.py` preparation
build as the parent. No fixture phases or altered retrieval rule are added.
The tool does not produce the roughly 228 GB PPMd-prior dataset and does not
launch training. Those are separate decisions and experiments.


The original run exposed a late-stream history-read bottleneck, captured in
[this point profile](20261017-late-read-profile-v1/report.json). The separately
[frozen read-cache diagnostic](20261017-read-cache-protocol-v1/protocol.json)
adds `--read-cache` and a different output directory. It must reproduce the same
published dump, and does not modify the pinned source or release binaries.
Mapping growth/cap/fallback and causal reads have compiled tests. Concurrent
single runs do not establish a production speedup.


The [complete native Mac dump](20261017-native-dump-v1/report.json) matches the
published row-file SHA-256 and all raster lengths. Its
[coverage summary](20261017-native-coverage-v1/report.json) counts 593,115,276
data rows, including 45,701,710 inserted rows and 31,821 unmasked alias rows
excluding author bytes. Categories overlap. The original analyzer incorrectly
rejected input sentinels 208–215; its [failure](20261017-coverage-analysis-failure-v1)
is retained, and the corrected reader validates sentinel/stream roles.

## Small final bit predictor

The [bit-level trace writer](20261017-bitl-trace-screen-v2) preserves both Mac
fixture archives. Its [runtime-math replay](20261017-bitl-replay-screen-v2)
matches every live integer probability on both fixtures; the
[native Linux replay](20261017-bitl-linux-screen-v1) independently passes with
the same linked math. The [earlier mismatch](20261017-bitl-linux-system-math-failure-v1)
is retained. Raw traces stay local, with their byte counts and hashes in the
reports.

The [frozen one-pass CPU experiment](20261017-bitl-warm-start-v1) selected a
7,386-byte BF16 model on the screen before checking the disjoint fixture.
Actual payload results for that fixed model are:

| Host | Screen baseline → trained | Disjoint baseline → trained |
| --- | ---: | ---: |
| [Native Mac](20261017-bitl-archive-screen-v1) | 119,065 → 118,917 B (−148 B) | [117,438 → 117,347 B (−91 B)](20261017-bitl-archive-holdout-v1) |
| [Native Linux](20261018-bit-weight-linux-screen-v1) | 119,067 → 118,931 B (−136 B) | [117,426 → 117,333 B (−93 B)](20261018-bit-weight-linux-holdout-v1) |

Every pair restores exact original XML with matching context counts. The
[packed Linux release comparison](20261018-bit-release-v1) reproduces the
published baseline executable and saves 16 bytes in `comp9` plus 16 bytes in
the independent decoder prefix, with the transformer-weight block unchanged.
These are small reused-fixture and component results, not a full prize score.

The same fixed one-pass checkpoint also saves [95 payload bytes on a third
Mac range](20261018-bit-weight-third-range-v1), with exact original XML
restoration and baseline-identical context counts. That range was already
used for a different retrieval experiment, so it is supporting evidence,
not a fresh final holdout. No weights were retuned to it.

On a separate 4,002,523-byte raw range, the fixed model saves [250 payload
bytes on native Linux](20261018-bit-weight-linux-broad-v1) against the
same-host baseline (476,220 → 475,970 B). Both complete archives restore the
original XML. The range is reserved for subsequent broader training and
cannot remain its holdout afterward.

The [extra-pass screen experiment](20261017-bitl-multi-pass-v1) is a recorded
rejection: its 16-pass checkpoint gains 282.3 further probability-cost bytes
on screen but loses 90.6 bytes on disjoint versus the one-pass model. A
[separate four-megabyte range](20261018-broad-trace-protocol-v1) is prepared
and being traced for broader training. It remains disjoint from the earlier
screen and disjoint fixtures; its raw files are reproducible and stay local.
