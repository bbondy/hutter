# Frozen interpolation passes both replay gates

The [predeclared blend protocol](protocol.json) tested just three BF16
interpolations between the earlier screen-trained checkpoint and the best
separate-range checkpoint, both descended from the same shipped model.
The loader re-exported both endpoints to byte-identical BF16 files before
interpolating. Every candidate remains 7,386 bytes and uses the unchanged
BITLSTM runtime.

| Broad checkpoint share | Screen probability cost vs prior |
| ---: | ---: |
| 25% (selected) | **−8.6 B** |
| 50% | −3.9 B |
| 75% | +5.9 B |

The 25% checkpoint was selected before one disjoint replay. It also saves
**31.3 probability-cost bytes** there versus the prior checkpoint, passing
both predeclared ≥1-byte gates. The selected BF16 file is
[`blend-1-of-4.nblb`](blend-1-of-4.nblb), SHA-256
`4369bf1abd259a42b4463f519d7613bd9c78c138e72c8c7d03c1f6170af2c0f4`.
The [report](report.json) retains all candidate hashes, replay logs,
source/protocol checks and the selection made before the holdout.

These are model-bit probability costs, **not actual archive bytes**. Both
evaluation fixtures have been reused, and the prior checkpoint trained on
the screen. A [separate archive protocol](../20261022-bitl-blend-archive-protocol-v1/protocol.json)
now freezes this one selected model for paired compression tests.
