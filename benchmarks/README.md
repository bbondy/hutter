# Benchmark history

Native/Linux compatibility checks are stored separately under `parity/<id>/`.
They retain initialization, probability-stream and cross-decoding outcomes,
including failed comparisons. See the [parity harness](../engines/ports/cmix-neif-parity/README.md).
These are correctness records, not eligible full-corpus prize scores.

`python3 scripts/parity_history.py list` shows completed paired fixture encodings.
`python3 scripts/parity_history.py compare BEFORE AFTER` reports payload-byte
changes only when both records use the same prepared input, article count, assets,
reference image and upstream source. Initialization-only, diagnostic-prefix and
decoder-only records remain accessible by ID but are not treated as scores.

Keep small experiment records in Git under `runs/<unique-id>/`. Each record has
the original metadata and JSONL trials, a note, and optionally the source patch
and corpus manifest. Run IDs cannot be overwritten. Large archives, executable
snapshots and logs stay in ignored `build/` directories. Save release artifacts
separately if they must survive cleanup; Git records preserve measurements, not
every generated archive.

```sh
make build
make samples
python3 scripts/benchmark.py data/samples/prefix-1m data/samples/middle-1m \
  --codecs ppmd ppmd-bit --repeats 3 --output build/experiment-001 \
  --record experiment-001 --note "Baseline before changing escape estimation" \
  --manifest data/samples/manifest.json

# Or record a completed run later:
python3 scripts/benchmark_history.py record build/experiment-001 \
  --id experiment-001 --note "Baseline before changing escape estimation" \
  --manifest data/samples/manifest.json

python3 scripts/benchmark_history.py list
python3 scripts/benchmark_history.py compare experiment-001 experiment-002
git add benchmarks/runs/experiment-001
git commit -m "Record baseline escape-estimation benchmark"
```

Choose either automatic `--record` or the later `record` command for a given ID.
Commit implementation changes before measuring when possible. For dirty tracked
source changes the runner captures a patch and source-file hashes; new untracked
model files still need a source commit to be reproducible. The executable is
copied into the run directory before trials, so rebuilds cannot change a run.

Comparisons match **input SHA-256 and codec**, exclude failed/nonrepeatable groups,
and show archive-byte differences, median compression/decompression time and peak
RSS differences. A changed sample path does not break matching; changed contents
do. Cross-machine timings produce a warning. For renamed experimental codecs,
inspect the individual JSONL records or retain a stable experimental codec name.
Compare the same compiler/flags and hardware for performance conclusions.

The initial `20261017-*` runs used codec source at `9821788`. They are exploratory,
mostly single trials, and were captured before the history feature existed.
Their original dirty-tree metadata is retained honestly; no clean-revision claim
is implied. See [the initial report](../docs/benchmarks/2026-10-17/README.md).
