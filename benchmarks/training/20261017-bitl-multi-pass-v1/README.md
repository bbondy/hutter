# More screen training overfits the disjoint fixture

The [frozen protocol](../20261017-bitl-multi-pass-protocol-v1/protocol.json)
continues the one-pass FP32 checkpoint at learning rate 0.003 for up to 16
total screen passes. Each full-trace invocation reloads the preceding weights
and resets Adam moments. Frozen BF16 checkpoints were measured only at passes
2, 4, 8 and 16; the best screen checkpoint was hashed in `selection.json`
before any disjoint evaluation.

| Total screen passes | Frozen screen cost change versus one pass |
| ---: | ---: |
| 2 | −64.8 B |
| 4 | −135.5 B |
| 8 | −204.9 B |
| 16 | −282.3 B |

The selected 16-pass model increases disjoint frozen cost by **90.6 bytes**
versus the one-pass model. It fails the predeclared holdout gate, so no archive
trial or alternative checkpoint selection follows. This supports moving to
broader training data rather than repeatedly fitting this small trace.

`report.json` holds commands, input and output weight hashes, compiler/build
identity, elapsed times and every loss. `verification.json` checks all 22
replay logs, the four exported BF16 and FP32 checkpoints, selection/protocol
hashes, and the completed negative gate. Every intermediate FP32 checkpoint,
all exported weights and logs are retained. These are probability costs,
not compressed archive bytes or a prize score.
