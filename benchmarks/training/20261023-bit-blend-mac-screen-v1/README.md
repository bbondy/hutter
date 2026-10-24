# Native Mac archive test: selected BITLSTM blend, screen

The frozen [three-way archive protocol](protocol.json) measured untouched,
prior one-pass and selected 25% blend checkpoints on identical prepared
input. All three restore the exact original XML and keep baseline-identical
encoder/decoder context counts.

| Payload | Untouched | Prior one-pass | Selected blend |
| --- | ---: | ---: | ---: |
| Screen | 119,065 B | 118,917 B | **118,908 B** |

The blend saves **9 bytes versus prior** and 157 versus untouched, with the
same 873,096-byte development-binary size. The disjoint [paired Mac
comparison](../20261023-bit-blend-mac-holdout-v1) also improves. Mac wall
times include laptop sleep and are not controlled speed measurements.
The [report](report.json) binds all inputs, assets, binaries, payloads,
contexts and exact restored XML by hash.
