# Training-data and prompt diagnostics

This history is separate from compression results. The upstream training tools
can emit the rows supplied to the transformer while skipping its forward pass.
Their constant-prediction output is not a valid compressed archive. A matching
dump establishes data reproduction; it does not prove a better trained model.

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
