# Native Linux archive test: selected BITLSTM blend, screen

[Workflow run 39870362623](https://github.com/bbondy/hutter/actions/runs/39870362623)
tested the frozen 7,386-byte 25% blend on the same native x86-64 host as the
untouched baseline and prior one-pass checkpoint. All three restored the
exact prepared input and original XML, with matching encoder/decoder and
baseline-identical context counters.

| Payload | Untouched | Prior one-pass | Selected blend |
| --- | ---: | ---: | ---: |
| Screen | 119,067 B | 118,931 B | **118,920 B** |

The blend saves **11 bytes versus prior** and 147 versus untouched. All three
development binaries are 577,272 bytes. The [downloaded artifact
verification](verification.json) independently passed 38 source, input,
archive, binary, restoration, context and log checks. The paired
[disjoint result](../20261023-bit-blend-linux-holdout-v1) also improves.
These are development payloads, not a complete release or prize score.
