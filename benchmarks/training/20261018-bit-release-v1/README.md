# Trained bit predictor reduces packed Linux release components

[Native Linux run 39096150448](https://github.com/bbondy/hutter/actions/runs/39096150448)
reproduced the published baseline `comp9` exactly (4,000,689 bytes, SHA-256
`8b07d85f0a374b55688fd08d1a464222f766efbb5bfefc2bc94d6abb201133d7`).
The candidate changes only the selected embedded BF16 bit-model array and its
hash comment. Both package builds pass all four upstream packer self-checks.

| Release component | Published baseline | Trained model | Change |
| --- | ---: | ---: | ---: |
| `comp9` compressor | 4,000,689 B | 4,000,673 B | −16 B |
| Independent decoder prefix | 165,545 B | 165,529 B | −16 B |
| Compressor + decoder prefix + required duplicate transformer-weight block | 7,882,901 B | 7,882,869 B | **−32 B** |

The external transformer-weight, hint and order blocks are byte-identical.
The existing selected model is 7,386 bytes in both builds; its changed values
happen to compress slightly better inside the packed program. The separate
native Linux fixture payloads save 136 and 93 bytes, but these small-payload
results and package components are not a full `enwik9` score.

The downloaded packages and decoder prefixes remain local. All reports, build
logs and selected toolchain record are committed. `verification.json` checks
the source revision, protocol, package and log hashes, packer results and an
independently repeated component comparison. The local binary hashes and
lengths are saved so the release package can be reproduced and checked later.
