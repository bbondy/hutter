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
