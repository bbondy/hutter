---
title: Train the small final bit predictor
description: A CPU training route with a compact model, missing trace tooling and strict replay checks.
---

# Train the small final bit predictor

The compressor has two distinct pretrained neural components. The transformer
predicts bytes; a much smaller LSTM adjusts the final bit probability after the
other models have mixed their predictions. The second model, called BITLSTM
upstream, ships only 7,386 bytes of bfloat16 weights. Improving its predictions
could reduce the data without adding another large model. That is a hypothesis,
not a measured gain here.

## What upstream actually trained

The [upstream training record](https://github.com/bbondy/hutter/blob/main/engines/cmix-neif/training/bitl/README.md)
uses 418,837,176 model bits from roughly the first 20% of the coder stream.
A model bit is one where this predictor runs; metadata, alphabet/grammar-fixed
bits and adaptive-depth skips make this different from a raw input-bit count. The 16-cell
model has 3,585 active parameters. Its weights stay frozen through that training
range, then begin learning online at a complete training-window boundary.

Upstream reports 32 offline passes taking 3 hours 10 minutes on one CPU core;
collecting the first 20% trace took about 14 hours. These are published costs,
not measurements on our hardware. It did not train offline on the entire
stream. A broader training range or a different compact correction model may
help, but could also worsen the already trained portion.

| Work | Main cost |
| --- | --- |
| Collect predictor inputs | A real compressor forward run, with all upstream model state |
| Replay and train this small model | CPU work over saved inputs; no transformer forward pass repeated |
| Ship the result | Model bytes plus executable changes, measured in the final package |

The correction never feeds back into the upstream predictor state. A correctly
recorded trace can therefore be reused across many bit-model settings. This is
why replay could make iteration much faster after the expensive first run.

## The missing piece is real

The public package contains the replay trainer and the final float32 checkpoint,
but **does not contain the original trace writer's development tree or the
trace itself**. Its trace shell script expects that missing tree. Running it
unchanged in this repository will not reproduce the training run.

The published 20% trace consists of 25,130,230,588 bytes of bit records and
14,449,882,600 bytes of channel records. The latter holds transformer and
byte-LSTM projections once per eight *model* bits. Full-stream storage could
be on the order of 200 GB if density scaled similarly; that is a planning
estimate, and the actual record count must be measured. This is offline
research data, separate from the final compressor's temporary-disk budget.

The float32 checkpoint can be converted back to the shipped bfloat16 array.
The [completed export audit](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-weight-audit-v1)
verifies its published hash, geometry, finite values, zero padding and exact
embedded bytes. The exported file and compiled array have the same SHA-256: `c72957f4…08a8e7d`. It does not regenerate the missing trace or
reproduce the original training.

## Reconstructing a trace writer

A [frozen fixture protocol](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-trace-protocol-v2)
now defines a diagnostic writer against the current runtime. It copies raw
mixer inputs and the projections the model already calculated, records each
observed bit and saves the corrected integer probability for replay comparison.
Channels follow the count of executed model bits, not raw byte boundaries.
Files use exclusive creation; a 16-million-model-bit cap fails explicitly if
exceeded. The upstream source remains unchanged in Git.
A preflight reader review corrected a mistaken four-zone validation limit: the
upstream enum defines six zones, including dictionary and title-mask zones.
The v2 protocols retain this correction and the original protocol hashes. The
compiled writer bytes are unchanged and are verified against their recorded
recipe revision; no recording run was replaced to make this correction.


The writer must leave the complete fixture archive unchanged, and encoder and
decoder must produce identical trace hashes. A matching file format alone does
not establish faithful replay or reproduce the historical training dataset.

The [replay protocol](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-replay-protocol-v3)
uses the public trainer with the exact shipped bfloat16 file. A diagnostic
freeze after its first observed bit prevents any complete backward window or
optimizer update. The driver compares every corrected integer probability,
then deliberately changes the first reference probability and requires a
mismatch at bit zero. Passing this checks frozen inference, not the later
online-training arithmetic or a new model's compression performance.

[Native Linux diagnostic checks](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-diagnostic-linux-checks-v1)
pass the compiled writer/driver controls and source-change guards. These are
synthetic checks; real model traces still need their own archive and replay
comparisons. A separate summary reports the current head's discrete-probability
cost by model-bit decile and recorded channel state. This can guide a later
experiment, but does not measure an archive with the head removed.

## First fixture results

Both Mac recordings preserve their entire baseline archive and restore the
original XML. Encoder and decoder produce identical trace/channel/probability
hashes. This gives 2,418,045 model bits on the screen and 2,399,939 on the
disjoint fixture. All recorded channel zones are zero in these two traces.

| Fixture | Archive bytes | Current head's probability-cost change | First trainer mismatch |
| --- | ---: | ---: | --- |
| Screen | 119,065, unchanged | −190.29 B | Bit 665,047: live 47,768, replay 47,767 |
| Disjoint | 117,438, unchanged | −222.39 B | Bit 281,491: live 59,892, replay 59,893 |

The [trace records](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-trace-screen-v2)
and [failed replay records](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-replay-screen-v1)
are saved with their disjoint counterparts. Replay stops at the first mismatch;
these are zero-based positions, not counts of all differences. The deliberate
wrong-probability controls also fail as intended. The probability-cost column
sums the current head's actual discretized predictions only where it executes;
it is not the size of an archive produced without that head.

**The math provider explains these Mac mismatches.** The compressor links its
own `exp`/`log` implementations from `detmath.cpp`; the standalone trainer used
system math. A [controlled diagnosis](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-math-diagnosis-v1)
reproduces the same first mismatches even with the runtime head, then matches
all 4,817,984 probabilities after linking the compressor's math code. The public
trainer also matches with that change. Inputs and weights remain unchanged.

The [formal v3 checks](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-replay-screen-v2)
now pass on both fixtures, including deliberately wrong first probabilities.
They explicitly bind the math source and its compile flags, enabling the
separately frozen CPU experiment. The earlier failures remain evidence: matching source formulas
and floating-point flags alone did not identify the linked math implementation.
Native Linux checks are separate from this Mac result.

## A staged experiment

1. Verify the unchanged checkpoint export and preserve its hashes.
2. Reconstruct a writer against the current runtime. Record exactly the model
   bits that execute, preserve the once-per-eight-model-bits channel rhythm,
   and keep dictionary pretraining and metadata behavior explicit.
3. On a canonical fixture, require an unchanged archive, exact XML restoration
   and identical encoder/decoder traces. Replay the shipped weights and compare
   every corrected integer probability with the live runtime.
4. Only after replay equivalence, freeze a training recipe and compare exported
   candidates. Training loss is a diagnostic; complete fixture archives decide
   promotion. Reused fixtures do not become fresh validation by being traces.
5. Collect broader/full-stream data on persistent native Linux hardware before
   claiming a competitive improvement. Record any revised point where online
   learning starts, total package cost, full restoration and runtime limits.

A [small warm-start protocol](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-warm-start-protocol-v2)
is prepared, gated on both fixture replay checks. It tries one screening-only
pass at learning rates 0.00003, 0.0003 and 0.003, each starting from the shipped
bfloat16 weights with fresh optimizer state. Selection uses frozen, exported
bfloat16 cost on the screen. The selected weight hash is saved before checking
that one model on the disjoint fixture; a failure does not trigger a switch to
a runner-up. Both probability costs must improve by at least one byte before
spending time on a real archive trial. Equal raw weight sizes still need packed
executable accounting later.

The [first CPU experiment](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-warm-start-v1)
is complete:

| Learning rate | Frozen screen cost change | Disjoint cost change |
| --- | ---: | ---: |
| 0.00003 | −11.9 B | Not evaluated |
| 0.0003 | −66.4 B | Not evaluated |
| 0.003 | −147.7 B | −91.2 B |

The selected model passes both probability-cost gates. Its shape and raw
7,386-byte size are unchanged. Each training pass took about 1.9 seconds in
this local run; a frozen replay took about 0.9 seconds. The expensive trace is
reused across all three settings. These timings describe this small replay
workload, not full compression performance.

A [separate archive protocol](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-archive-protocol-v1)
embeds that exact model hash and changes only its weight header. The completed
native Mac archive comparisons pass the predeclared promotion gate:

| Fixture | Baseline payload | Trained payload | Change | Original XML |
| --- | ---: | ---: | ---: | --- |
| [Screen](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-archive-screen-v1) | 119,065 B | 118,917 B | −148 B | Exact restoration |
| [Disjoint](https://github.com/bbondy/hutter/tree/main/benchmarks/training/20261017-bitl-archive-holdout-v1) | 117,438 B | 117,347 B | −91 B | Exact restoration |

All context counters match their baselines. Both development binaries are
873,096 bytes, though packed release package cost remains unmeasured. The
model was selected on the screen before the disjoint archive was tested.
That second fixture has been used in earlier research, so it is a useful
generalization check rather than untouched validation. Native Linux and a
longer stream are the next gates; these savings are far below a demonstrated
full-corpus prize margin.

The [training-row dump](training-data.md) is a different dataset: it cannot
replace the final mixer's bit-level inputs. A changed transformer also
requires a new bit-model trace, because its features and upstream predictions
change.
