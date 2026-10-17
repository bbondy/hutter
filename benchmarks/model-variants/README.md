# Controlled model comparisons

Save protocols before measuring, then retain every candidate's input, build,
asset, archive and restoration evidence, including regressions. These runs use
the native development port and measure fixture payloads, not prize scores.

The first protocol changes one link-context parameter at a time on the exact
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
  --protocol benchmarks/model-variants/20261017-protocol-v1/protocol.json \
  --manifest build/project-screen-v2/manifest.json --role screen \
  --build build/native-fixture-v3 \
  --runs build/project-screen-upstream-v1 build/model-screen-z3-budget128-v1 \
         build/model-screen-z3-chunk32-v1 build/model-screen-z3-off-v1 \
  --output benchmarks/model-variants/20261017-screen-v1
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
