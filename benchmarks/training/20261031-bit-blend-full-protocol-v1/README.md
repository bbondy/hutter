# Frozen full enwik9 baseline and blend comparison

This [protocol](protocol.json) binds the published untouched release and the
selected 25% BITLSTM blend to the exact 1,000,000,000-byte enwik9 input.
There are **no full-run results** under it yet. Both Linux packages were
reproduced in [run 40187845193](https://github.com/bbondy/hutter/actions/runs/40187845193):
untouched `comp9` is 4,000,689 bytes, SHA-256
`8b07d85f0a374b55688fd08d1a464222f766efbb5bfefc2bc94d6abb201133d7`;
blend `comp9` is 4,000,656 bytes, SHA-256
`d448abd6ceb1c143aacc1793d119b01700e863fa86bcc081531790179eb96f39`.
The [saved release comparison](../20261025-bit-blend-release-v1) verifies the
source/model bindings and identical external blocks.

On an idle persistent native Linux x86-64 host with AVX2 and FMA, official
enwik9, the two verified packages and enough free disk, run the published
baseline first. Choose an allowed logical CPU; `0` below is illustrative:

```sh
python3 scripts/release_full.py \
  --binary build/ci-bit-blend-release-v1/blend-release-baseline/comp9 \
  --enwik9 data/enwik9 \
  --protocol benchmarks/training/20261031-bit-blend-full-protocol-v1/protocol.json \
  --role baseline --cpu 0 --output build/full-bit-blend-baseline-v1
```

Require the published archive hash, exact isolated SFX restoration and saved
resource record. Then run the frozen blend with the same host and procedure:

```sh
python3 scripts/release_full.py \
  --binary build/ci-bit-blend-release-v1/blend-release-candidate/comp9 \
  --enwik9 data/enwik9 \
  --protocol benchmarks/training/20261031-bit-blend-full-protocol-v1/protocol.json \
  --role candidate --cpu 0 --output build/full-bit-blend-candidate-v1
```

The script records the complete SFX archive, compressor, required arguments,
original-output hash and per-phase resource samples. Save both outcomes,
including any failure or regression. A complete verified comparison is needed
before quoting a prize-sized improvement. The earlier 4 MB fixture saves
126 payload bytes versus the prior checkpoint; that does not predict the full
enwik9 result or prove resource and license eligibility.

No persistent native Linux host is configured for this repo. The current
hosted CI workflow has a 330-minute timeout, shorter than the published
tens-of-hours per phase.
The binaries can be rebuilt exactly with `release-bit-blend.yml` after its
temporary artifact expires; the hashes above remain the acceptance gate.
