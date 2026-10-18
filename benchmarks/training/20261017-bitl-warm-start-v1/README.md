# First CPU warm-start screen: one candidate survives probability-cost gates

All candidates start independently from the shipped BF16 checkpoint and receive
one pass over the 2,418,045-model-bit screening trace. The compressor's own
deterministic math is linked. Frozen BF16 evaluation selects only on screen.
The selected weight hash was written to selection.json before its holdout run.

| Learning rate | Screen cost change | Disjoint cost change |
| --- | ---: | ---: |
| 0.00003 | -11.9 B | Not evaluated |
| 0.0003 | -66.4 B | Not evaluated |
| 0.003 | -147.7 B | -91.2 B |

These are upstream rounded probability-cost diagnostics, not archive bytes.
The selected 7,386-byte model is models/lr3000.nblb, SHA-256
`bfd6401b0142441e7b99a4fe930943d830e7dca2e47d08692e83b023a642f8e0`.
No model geometry changes. All FP32/BF16 checkpoint hashes, logs, source and
compiler identity are retained, including the other candidates. The model
files derive from the pinned cmix-neif BITLSTM weights and trainer; preserve
its license and attribution when using them.

Each pass took about 1.88-1.90 seconds in this local run, and each frozen
evaluation about 0.9 seconds. These describe small replay runs, not full
compression throughput or a controlled hardware benchmark. This candidate
is eligible for an embedded-model archive trial, followed by Linux and full
package/corpus verification if successful. It is not yet a prize gain.
