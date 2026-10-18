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
