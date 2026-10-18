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

## Canonical-input results on Mac and native Linux

The corrected inputs now match byte for byte across platforms. All sixteen
model/input/platform trials restore the original XML and match encoder/decoder
context counters. Each table compares against its own platform baseline.

| Model | Mac screen | Change | Mac disjoint | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream settings | 119,065 | — | 117,438 | — |
| Half total budget | 119,077 | +12 | 117,448 | +10 |
| Shorter chunks | 119,077 | +12 | 117,442 | +4 |
| Link prefixes disabled | 119,084 | +19 | 117,454 | +16 |

| Model | Linux screen | Change | Linux disjoint | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream settings | 119,067 | — | 117,426 | — |
| Half total budget | 119,070 | +3 | 117,436 | +10 |
| Shorter chunks | 119,076 | +9 | 117,433 | +7 |
| Link prefixes disabled | 119,086 | +19 | 117,456 | +30 |

All sizes are fixture payload bytes, including the common 16-byte development
frame. **Every candidate loses on both fixtures and both platforms.** Keep the
upstream settings for the next experiments. The remaining Mac/Linux numerical
differences change small byte deltas, but they do not change this decision.
These sparse fixtures do not estimate the full-corpus value of link retrieval.

Saved evidence: [Mac screen](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-screen-v2/report.json),
[Mac disjoint](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-holdout-v2/report.json),
[Linux screen](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-linux-screen-v2/report.json)
and [Linux disjoint](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-linux-holdout-v2/report.json).
The Linux workflow runs all four models serially on each fixture's host. Its
single-trial timings are useful for planning; the concurrent Mac trials do not
support a hardware speed comparison. Downloaded artifact hashes and independent
Mac inverse preparation also verify the Linux results.

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

## Follow-up: retrieve the correct link target

The budget tests above reduced how much context the model received. A separate
[frozen experiment](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-protocol-v1/protocol.json)
changes which links qualify. The upstream README explicitly lists an unmeasured
opportunity: a link to a longer title can currently qualify for the shorter
article whose title is its prefix.

The new candidate requires the existing exact title match to end at a closing
bracket, link pipe or section marker, already available to the decoder. A link
to `University of ...` therefore stops qualifying merely as `University`.
Case folding and underscore handling stay as they were. Budgets, weights,
article order and all other model settings remain fixed.

This may remove noise, but the frozen model was trained with the original
retrieval rule, so an improvement is not guaranteed. The candidate must restore
all original bytes, show matching context counters and improve both reused
fixtures before promotion.

The first paired Mac measurements clear that screening rule:

| Model | Screen payload | Change | Disjoint payload | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream matching | 119,065 | — | 117,438 | — |
| Exact target boundary | 119,060 | −5 | 117,436 | −2 |

Both restore original XML exactly and reproduce encoder context counters during
decoding. The filter changes actual retrieval: screen mentions fall from 88 to
84 and prefix tokens from 1,893 to 1,775; disjoint mentions fall from 50 to 41
and tokens from 1,361 to 1,145. The source verifier permits only the frozen
`tf1_z3.cpp` rewrite and checks all other compiled sources and assets.

Saved evidence: [screen](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-screen-v1/report.json)
and [disjoint](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-holdout-v1/report.json).
These tiny gains justify testing the unchanged candidate on native Linux and
the reserved third range. They do not establish a full-stream gain, and a
different platform has already reversed similarly small gains in the
[depth experiment](adaptive-depth.md). Concurrent timings do not establish a
speed improvement.

Native Linux confirmation reverses the disjoint result:

| Model | Linux screen | Change | Linux disjoint | Change |
| --- | ---: | ---: | ---: | ---: |
| Upstream matching | 119,067 | — | 117,426 | — |
| Exact target boundary | 119,064 | −3 | 117,431 | +5 |

Both trials restore the original XML exactly, with matching context counters.
Downloaded binaries, archives, decoded inputs and logs were checked locally;
the baseline Linux source inventory was reconstructed and the exact candidate
rewrite verified. Saved evidence:
[Linux screen](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-linux-screen-v1/report.json)
and [Linux disjoint](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-linux-holdout-v1/report.json).
The candidate **does not improve both Linux fixtures** and fails
promotion. The already-started reserved-range trials were completed without
retuning; a good third result does not erase this regression.

The [reserved-range protocol](https://github.com/bbondy/hutter/tree/main/benchmarks/model-variants/20261017-retrieval-confirmation-protocol-v1)
froze a third input before measuring it: 150 complete articles beginning
at raw byte 80,020,050, selected by the previously declared 80,000,000-byte
start and one-million-byte target. It preserves upstream projected order and
all existing model settings. After this test, that range is examined evidence
and cannot serve as untouched validation for further tuning.

The [Mac third-range result](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-confirmation-v1/report.json)
also loses: 125,996 bytes against the baseline's 125,991, a **5-byte increase**.
Both restore all 1,000,794 original XML bytes. The filter removes two retrieved
mentions (16 → 14) and reduces prefix tokens from 702 to 626; it changes actual
context rather than acting as a no-op. This previously reserved check therefore
supports keeping the original rule. The
[Linux third-range result](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-retrieval-linux-confirmation-v1/report.json)
saves **2 bytes**: 125,999 against 126,001. Both Linux models also restore the
original XML, with matching context counters and independently checked artifact
hashes. All six comparisons are now recorded. The Linux third-range gain does
not override the Linux disjoint loss or the Mac third-range loss: **keep the
original retrieval rule under this protocol**.

## Separate follow-up: refresh the prediction after alias text

The upstream notes identify another mismatch. The compressor feeds some alias
text only to the transformer. After the last alias byte, its mixer still uses
the transformer prediction from before that block for the next real byte,
although training targets that byte with the last alias row.

The [alias-refresh protocol](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-alias-protocol-v1/protocol.json)
tests that one callback: update the transformer's mixer slot and its cached
first-bit probability after the final eligible alias row. It preserves the
other predictors, priors, weights, retrieval rule and input. A small compiled
callback probe checks final-row handling and gates; actual compression results
are still required. This is separate from exact-target filtering and will use
the original model as its control.
