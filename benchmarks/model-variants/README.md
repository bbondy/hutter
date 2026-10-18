# Controlled model comparisons

Save protocols before measuring, then retain every candidate's input, build,
asset, archive and restoration evidence, including regressions. These runs use
the native development port and measure fixture payloads, not prize scores.

Protocol v2 establishes fresh baselines after the XML entity portability fix.
It keeps the same raw pages, permutations and model settings as v1; only prepared
bytes change to match Linux. The old v1 records remain labeled with their earlier
Mac representation and must not be used as canonical-input baselines.

The experiment changes one link-context parameter at a time on the exact
upstream-projected screen and follow-up inputs. Its baseline encodings are
shared with the article-order experiment. Frozen weights remain unchanged;
inference-time changes may disagree with the training distribution.

Named variants are applied only to disposable source copies, with the original
and modified header hashes saved in `build.json`. Build either platform with
the same recipe:

```sh
python3 scripts/native_cmix.py build --variant z3-budget128 --output build/native-z3-budget128
python3 scripts/cmix_parity.py build-linux --variant z3-budget128 --output build/linux-z3-budget128
```

Platform parity checks reject different model recipes. The `z3-off` control
sets prefix budget to zero, preserving the upstream mention index and all other
context channels. It does not establish a memory reduction. Candidate archives
must be decoded with the matching candidate binary; the development frame
stores corpus phases, not a model identifier.

Run each candidate with `native_cmix.py bench` against the protocol's exact input
and manifest. After all four models finish, save the comparison with:

```sh
python3 scripts/model_history.py \
  --protocol benchmarks/model-variants/20261017-protocol-v2/protocol.json \
  --manifest build/project-screen-v4/manifest.json --role screen \
  --build build/native-fixture-v4 \
  --runs build/project-screen-upstream-v2 build/model-screen-z3-budget128-v2 \
         build/model-screen-z3-chunk32-v2 build/model-screen-z3-off-v2 \
  --output benchmarks/model-variants/20261017-screen-v2
```

The verifier checks generated source inventories, compiler settings, assets,
phase arguments and the benchmark function from each recorded Git revision.
Build parallelism and documentation may differ; compiled sources may differ only
in the declared parameter header. It rechecks local archives, decoded streams,
context reports and original article bytes before saving every model's result.
Required executable sizes are recorded separately; fixture payload deltas still
cannot establish packaged prize savings.

## Native Linux confirmation

The manually triggered
[Linux fixture workflow](../../.github/workflows/linux-benchmarks.yml) uses
standard Ubuntu 24.04 x86-64 runners. It runs all four fixed variants serially on
each fixture's host, with original x86 kernels, Linux paging and upstream PGO/LTO
flags. `replay_fixture.py` reconstructs the saved article permutations and refuses
any prepared byte that differs from the Mac fixture. The shared verifier checks
all original article bytes after decoding. No Docker is required on the runner.

```sh
gh workflow run linux-benchmarks.yml --ref main
```

The workflow also independently checks the upstream full-corpus training stream
in preparation-only mode, to investigate the saved Mac mismatch. It does not run
the full adaptive enwik9 compressor. Artifacts include failed trials and expire
after seven days; download the small verified reports and commit them into this
history before expiry. Keep the GitHub run URL and source revision with them.

This repository is public. GitHub currently provides standard Linux x64 runners
with 4 CPUs and 16 GB RAM free for public repositories; each hosted job is limited
to six hours ([runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[limits](https://docs.github.com/en/actions/reference/limits)). These are useful
for bounded fixture experiments, not the published full-run time requirement.
Compiler/libc versions are recorded; the runner's package set is not asserted to
match the upstream submission's pinned Ubuntu snapshot.

## Adaptive-depth experiment

[The depth protocol](20261017-depth-protocol-v1/protocol.json) tests threshold 9
and disabling adaptive skips (threshold 31, above the clamped logit range) against
the default 8. Both reuse the exact canonical inputs and default link context.
The recipe changes only `src/adaptive_depth.h`; the verifier checks its original
baseline hash and rejects any other source change. Model weights and learning
rules remain fixed, but mixer training receives a different set of bits.

Build with `--variant depth-tau9` or `--variant depth-no-skip`. Use the same
`model_history.py` command with this protocol and exactly three run directories:
baseline, threshold 9, and no adaptive skip. Preserve all outcomes, not just gains.
The no-skip control retains the small gate's computation and the independent
character-rate shortcut. Neither fixture size nor concurrent timing establishes
full-run value; upstream's estimated size tradeoff is small.

The Linux workflow accepts an explicit experiment:

```sh
gh workflow run linux-benchmarks.yml --ref main -f experiment=adaptive-depth
```

It runs the three models serially per fixture and omits the unrelated full-stream
preparation job. Both experiment families remain manual dispatches.

## Exact link-target follow-up

The [frozen retrieval protocol](20261017-retrieval-protocol-v1/protocol.json)
requires a decoded target delimiter after the existing exact title match.
Native Mac [screen](20261017-retrieval-screen-v1/report.json) and
[disjoint](20261017-retrieval-holdout-v1/report.json) results save 5 and 2 payload
bytes respectively, with exact raw restoration and matching context counters.
The candidate passes the predeclared screening rule; keep its recipe unchanged
for native Linux and reserved-range confirmation. These are small fixture gains,
not a package-size or speed claim.

```sh
gh workflow run linux-benchmarks.yml --ref main -f experiment=exact-target
```

Builds use `--retrieval-variant exact-target`; source comparison checks the
declared `tf1_z3.cpp` rewrite rather than the parameter-header recipes above.

Native Linux [screen](20261017-retrieval-linux-screen-v1/report.json) and
[disjoint](20261017-retrieval-linux-holdout-v1/report.json) save 3 and lose 5 bytes
respectively. Both restore exactly, and downloaded evidence has been verified
again locally. The candidate fails the Linux promotion gate. The already-started
reserved-range runs are retained without changing the recipe or using a
third result to erase this regression.

The [previously reserved Mac range](20261017-retrieval-confirmation-v1/report.json)
also loses by 5 bytes: 125,996 versus 125,991, with exact restoration and matching
context counters. The unchanged filter is rejected on both the Linux disjoint
gate and this additional range. The completed
[Linux third range](20261017-retrieval-linux-confirmation-v1/report.json) saves
2 bytes (125,999 versus 126,001), with exact restoration. That result does not
override the failed gates; all six comparisons are retained.

## Alias prediction refresh

The [alias protocol](20261017-alias-protocol-v1/protocol.json) changes only
`Predictor::ObserveTfOnlyByte`: after the final alias row, refresh the transformer
slot and its cached first-bit probability. Other model state and the PPMd prior
stay unchanged. Build with `--alias-variant refresh`; the same source guard
checks the exact rewrite and rejects combining it with weights, retrieval or
parameter changes. A compiled callback probe tests final-row and gate behavior.
The completed [screen](20261017-alias-screen-v1/report.json) adds 4 bytes
(119,069 versus 119,065), and the [disjoint](20261017-alias-holdout-v1/report.json)
ties at 117,438. Both restore original XML and preserve all context counts.
This fails the frozen both-fixture improvement requirement: no Linux or larger
promotion under this protocol. The original callback remains the control.


## MLP activation diagnostics

The [frozen activity protocol](20261017-activity-protocol-v1/protocol.json) uses
`--activity-variant mlp`. It leaves all model settings fixed and requires archive
identity, original-byte restoration and identical encoder/decoder counters.
After saving its comparison with `model_history.py`, summarize it with:

```sh
build/weight-audit-env/bin/python scripts/mlp_activity_summary.py \
  --comparison benchmarks/model-variants/20261017-activity-screen-v1 \
  --pruning-record benchmarks/weights/20261017-pruning-containers-v1 \
  --output benchmarks/weights/20261017-activity-screen-summary-v1
```

The summary relates measured activation moments to the already rejected removal
maps. Its per-neuron squared-contribution score is a diagnostic, not coding loss;
adding these scores omits cross-neuron correlations. No new removal is authorized
by this data alone, and observed inactivity is not universal deadness.


Both MLP activity comparisons now pass: [screen](20261017-activity-screen-v1/report.json)
and [disjoint](20261017-activity-holdout-v1/report.json) reproduce baseline
archives exactly and have matching encoder/decoder counters. All 12,218 neurons
activate in each fixture. The [summaries](../weights/20261017-activity-screen-summary-v1)
show that the old 5% weight-norm removals can include about 17% of a layer's
squared activation mass. These diagnostics do not themselves change the model.
