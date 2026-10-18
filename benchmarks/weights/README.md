# Weight-container experiments

The submission carries transformer weights in both executables, so reducing
one container can help twice. Counts here are container bytes, not packaged
prize savings: binding data and compressed executable sizes must also be checked.

The first experiment permutes MLP hidden neurons. For each layer, it applies
the same permutation to the up-projection rows, their scales, and the
down-projection columns. This preserves the mathematical network. The actual
integer kernels, floating-point epilogues and full coder still need verification
before claiming identical predictions or archives.

Three stable ascending sort keys are fixed before measuring: absolute up-row
scale, number of zero up-row weights, and sum of up-row weights. Each changes
only the representation of the shipped model. No corpus scores select the order.
An upstream container rewrite must first be byte-identical; every candidate
must read back exactly and its inverse permutation must recover all tensors.

```sh
python3 -m venv build/weight-audit-env
build/weight-audit-env/bin/python -m pip install numpy==2.5.4
build/weight-audit-env/bin/python scripts/weight_permutation.py \
  --protocol benchmarks/weights/20261017-permutation-protocol-v1/protocol.json \
  --output build/weight-permutations-v1
```

The exact NumPy/Python versions, pinned upstream writer, recipe and input hashes
are recorded. Containers remain in ignored build output; reports and permutation
maps belong in Git. Save every candidate, including regressions. Any candidate
requires kernel equivalence checks on both platforms and unchanged coder traces
before full package accounting.

The [first container results](20261017-container-permutations-v1/report.json)
save 4,280 bytes for scale order, 1,676 for zero-count order and 938 for row-mean
order. All three pass exact container rewriting and tensor reconstruction.
These numbers alone do not establish inference equivalence.

The kernel probe compiles the actual MLP kernels and loader from a verified
development build, using that build's compiler and per-file transformer flags:

```sh
python3 scripts/weight_kernel_probe.py --build build/native-fixture-v4 \
  --original engines/cmix-neif/weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4 \
  --candidates build/weight-permutations-v1/mlp-scale.c4 \
               build/weight-permutations-v1/mlp-zero-count.c4 \
               build/weight-permutations-v1/mlp-row-mean.c4 \
  --output build/weight-kernels-v1
```

It checks 1,024 synthetic activation vectors per layer, including range extremes,
and forces both sparse and dense down-projection paths. All output float bits
and nonzero counts must agree. This is a bounded kernel test; complete coder
traces and package accounting remain separate checks.

## Complete archive equivalence

[The archive protocol](20261017-archive-protocol-v1/protocol.json) selects the
smallest container above (`mlp-scale`) before looking at any coder result. Both
canonical fixtures must produce archives identical to their original-container
baselines and restore the exact raw XML. Development builds accept an explicit
`--weight-container`; they stamp its fingerprint and keep the runtime check.

```sh
python3 scripts/native_cmix.py build \
  --weight-container build/weight-permutations-v1/mlp-scale.c4 \
  --output build/native-weight-scale-v1
```

Run `native_cmix.py bench` with this build on each frozen input, then verify with
`weight_equivalence.py`. The verifier permits only the container file and the
exact fingerprint constant to differ, checks all assets and logs, and reverses
preprocessing and page order before saving a result. It preserves valid round
trips whose archives differ as failed equivalence checks.

The [manual Linux workflow](../../.github/workflows/weight-comparisons.yml)
recreates all three containers, checks their actual x86 kernels and runs the
baseline/candidate pair serially on each fixture host. It saves failure evidence
as well as completed comparisons; download and commit the reports within the
seven-day artifact lifetime.

```sh
gh workflow run weight-comparisons.yml --ref main
```

## Real release packaging

The separate `release-packages.yml` workflow builds the untouched upstream
release package and the weight-bound candidate with the original `build.sh`.
It keeps the original PGO/LTO, section-cut guards, packer, and both real-stub
unpacking checks. It uses neither development fixture phases nor a Docker build.

`package_structure.py` partitions the actual compressor, constructs its decoder
prefix exactly as upstream does, and counts compressor + decoder prefix + the
archive's weight copy. Its decoder-prefix bytes have been checked against the
upstream C cut tool on the published binary. `package_compare.py` verifies both
actual binaries again before reporting component deltas.

These counts deliberately exclude the compressed dictionary, full enwik9 payload,
archive footer and invocation arguments. They establish a measured packaging
component delta; a full corpus run still decides the complete score. The native
Linux baseline report also checks whether the rebuilt compressor matches the
published SHA-256, without assuming the hosted runner has the pinned package set.

```sh
gh workflow run release-packages.yml --ref main
```
