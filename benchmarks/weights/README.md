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

## First native Linux results

Both [screen](20261017-linux-screen-v1/report.json) and
[disjoint](20261017-linux-holdout-v1/report.json) comparisons pass archive identity,
context equality and exact original XML restoration. Their kernel subdirectories
save all three candidates' passing native x86 checks. Both hosts recreate the
same containers as Mac; fixture payloads are 119,067 and 117,426 bytes.

The [real release comparison](20261017-linux-packages-v1/comparison.json) measures
an 8,560-byte reduction in compressor + decoder prefix + archive-side weights.
The packed program and decoder prefix retain their sizes, and each weight copy
shrinks by 4,280 bytes. The baseline compressor does not match the published
binary; package and compiler-selection evidence is retained separately. The
full enwik9 payload, dictionary and resource limits remain unverified.

The [unchanged-container audit](20261017-container-audit-v1/README.md) attributes
all bytes to tensor families and separates fitted entropy diagnostics from
achievable coding gains. Its observer must reproduce the original container
byte for byte before publishing any accounting.

The [Mac screen](20261017-native-screen-v1/report.json) and
[Mac disjoint](20261017-native-holdout-v1/report.json) also pass exact archive
identity against their own baselines (119,065 and 117,438 bytes) and original XML
restoration. Full-corpus inference equivalence is still a separate gate.

The [GCC 13 release comparison](20261017-linux-packages-gcc13-v1/comparison.json)
now reproduces the published baseline executable exactly. Removing the hosted
image's GCC 14 development packages changes Clang's selected C++ toolchain to
GCC 13. Against this baseline the candidate saves **8,563 component bytes**:
4,282 in the compressor, one in the decoder prefix, and 4,280 in archive weights.
The earlier GCC 14 paired result stays separate. Full release payload equivalence
and complete resource eligibility have not yet been established.

## Bounded full-input release check

The [release-prefix protocol](20261017-release-prefix-protocol-v1/protocol.json)
freezes the reproduced published compressor and the GCC 13 weight-bound binary.
`release-prefix.yml` runs both on official full enwik9, serially on one native
Ubuntu host, and deliberately stops each after one MiB of emitted coder output.
It compares those bytes by hash, the entire prepared stream and the compressed
dictionary. Equal prefix lengths alone are not evidence of equivalence.

This exercises the actual release packages beyond the development adapter.
It is intentionally incomplete: the prefix cannot be decoded as a full archive,
there is no full compression ratio, and sampled prefix resources do not establish
eligibility. The complete encoder run and independent SFX decode remain required.
The artifact source expires after seven days; retain the downloaded release pair
locally and rebuild it with the frozen recipe for later repeats.
