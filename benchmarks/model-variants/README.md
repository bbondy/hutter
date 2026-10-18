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
reserved-range runs will be retained without changing the recipe or using a
third result to erase this regression.
