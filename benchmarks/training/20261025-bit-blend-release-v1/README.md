# Blended bit predictor reduces packed Linux release components

[Native Linux run 40187845193](https://github.com/bbondy/hutter/actions/runs/40187845193)
built the untouched, prior one-pass and selected 25% blend releases from signed
commit `c10edcf`. The untouched and prior `comp9` SHA-256 values exactly match
the previously saved releases. All three pass the four upstream packer checks.
The blend changes only the embedded 7,386-byte BF16 bit-model header; external
transformer weights, hints and order blocks remain byte-identical.

| Release component | Untouched | Prior one-pass | Blend | Blend vs prior |
| --- | ---: | ---: | ---: | ---: |
| `comp9` compressor | 4,000,689 B | 4,000,673 B | 4,000,656 B | −17 B |
| Independent decoder prefix | 165,545 B | 165,529 B | 165,509 B | −20 B |
| Compressor + decoder prefix + duplicate transformer-weight block | 7,882,901 B | 7,882,869 B | 7,882,832 B | **−37 B** |

The blend saves 69 measured component bytes versus untouched. Its paired
native Linux fixture payloads also save 11 and 30 bytes versus prior, with
exact XML restoration and identical context counts. These are development
fixture payloads and executable components, **not a full enwik9 submission
score**; dictionary, payload, footer and arguments remain unmeasured together.
The gains are small relative to the roughly 1% prize threshold. Full-stream
compression, independent self-extracting decode, resources and eligibility
remain open.

The frozen [protocol](../20261024-bit-blend-release-protocol-v1/protocol.json),
three [release reports](baseline/report.json), bounded build logs,
[component comparison](blend-release-comparison.json) and
[verification record](verification.json) preserve source, model, binary, asset
and result hashes. Downloaded binary artifacts remain local and on GitHub
Actions for seven days; their lengths and SHA-256 values are recorded for
future reproduction. The local comparator reproduced the CI result byte for
byte from the downloaded binaries.
