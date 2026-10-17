---
title: Does retrieved link context help?
description: Separate article ordering from the value of the context supplied to a frozen compression model.
---

# Does retrieved link context help?

An earlier Wikipedia article may mention the article we are about to encode.
The compressor can retrieve text around that mention and feed it to the
transformer before predicting the new article's body. The decoder has already
restored that earlier text, so it can retrieve the same context without storing
the text again in the archive.

This is useful only if it improves predictions. A loosely related mention can
occupy attention space, and every extra token costs computation. The model was
also trained with a particular context format. Changing that format can hurt a
trained model even when the new information looks relevant to a reader.

## The frozen comparison

The [article-order experiment](article-order.md) changes which mentions are
available. This experiment holds the order and input bytes fixed and changes
how much of the available text the model receives.

| Model | Total prefix budget | Tokens per retrieved chunk | Question |
| --- | ---: | ---: | --- |
| Upstream settings | 256 | 64 | Baseline |
| Half total budget | 128 | 64 | Do fewer retrieved chunks predict better? |
| Shorter chunks | 256 | 32 | Does tighter context around each mention help? |
| Link prefixes disabled | 0 | 64, unused | How much does this trained model rely on the channel? |

The total budget includes separators. Both existing article sets use a projection
of the verified upstream order. Dictionary, weights, other model settings and
fixture phases stay fixed. The
[predeclared protocol](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-protocol-v1/protocol.json)
records the exact inputs. The first native results were:

| Model | Screen payload | Change | Disjoint payload | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream settings | 119,868 bytes | — | 118,442 bytes | — |
| Half total budget | 119,871 bytes | +3 bytes | 118,450 bytes | +8 bytes |
| Shorter chunks | 119,878 bytes | +10 bytes | 118,444 bytes | +2 bytes |
| Link prefixes disabled | 119,885 bytes | +17 bytes | 118,458 bytes | +16 bytes |

All eight model/input pairs restore original XML exactly, with matching context
counters; the disabled model feeds zero link-prefix tokens. No candidate improves
either fixture. The [screen record](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-screen-v1/report.json)
and [disjoint record](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-holdout-v1/report.json)
retain every result.

These trials used the earlier Mac entity representation. The later
[preprocessing portability fix](native-parity.md) changes prepared bytes, so
[protocol v2](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-protocol-v2/protocol.json)
re-establishes baselines on matching Mac/Linux inputs. Raw pages, permutations,
weights and model settings stay fixed; the third confirmation range remains
untouched. Earlier fixture losses are not full-corpus ablation estimates.

The disabled control keeps the mention index and other context channels. It
measures removing link prefixes from this trained model, not the best possible
model trained without them, and does not establish a memory optimization.

## What counts as evidence

Every candidate must restore the prepared stream and original XML bytes exactly.
Encoder and decoder must report identical context counters; the disabled control
must feed zero link-prefix tokens. Comparisons reject source changes outside the
declared parameter header, different compiler settings or different assets.
The [saved model records](https://github.com/bbondy/hutter/tree/main/benchmarks/model-variants)
retain regressions alongside gains.

These are sparse, repeatedly examined fixtures. A candidate that improves both
must face the reserved third range, Linux comparison and full-pipeline accounting.
A payload improvement here does not establish a Hutter Prize score. See the
[experiment playbook](experiment-playbook.md) for those promotion checks.
