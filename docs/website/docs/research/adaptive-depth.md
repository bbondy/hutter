---
title: Spend more computation on confident bits?
description: Test the compression and runtime tradeoff of skipping the expensive mixer cascade.
---

# Spend more computation on confident bits?

The compressor combines predictions from many models. Before its expensive
mixer cascade, a small online model decides whether it is already confident
enough to predict a bit. If its confidence exceeds a threshold, the compressor
uses that prediction and skips the cascade, secondary estimation and BITLSTM
correction for that bit. Both encoder and decoder make the same decision from
the same earlier data.

The pinned upstream documentation reports about 5.1% fewer instructions for a
small compression cost: roughly 2.7 KB on one 80 MB window, extrapolated there
to about 18 KB on the full stream. Those are upstream measurements, not results
reproduced here. They suggest a bounded experiment: spend a little more time
and check whether it recovers bytes. Even the upstream estimate is far too
small to make this a complete prize-winning strategy.

## A frozen three-model comparison

| Model | Skip threshold | What changes |
| --- | ---: | --- |
| Upstream settings | 8 | Baseline |
| Stricter confidence | 9 | Fewer bits qualify for the shortcut |
| Adaptive skips disabled | 31 | The gate's logit is clamped to ±30, so it cannot pass this threshold |

The [saved protocol](https://github.com/bbondy/hutter/blob/main/benchmarks/model-variants/20261017-depth-protocol-v1/protocol.json)
fixes both canonical article inputs and the exact changed source hashes before
measurement. Each candidate changes one constant. Dictionary, weights, link
context, learning rules and compiler settings stay fixed. No results are claimed
yet; the experiment must retain losses as well as gains.

More computation need not improve compression. The shortcut also determines
which bits train the mixer and BITLSTM, so changing it changes their future
state. The disabled control still computes and trains the small gate, and a
separate character-rate shortcut remains active. This is a test of routing more
bits through the cascade, not a complete removal of shortcuts or gate overhead.

Every candidate must restore the original XML exactly. A gain on both reused
fixtures earns a test on the reserved third range and a native Linux comparison.
Concurrent Mac timings are exploratory; a useful size/time tradeoff needs paired
serial timings and ultimately the full submission's runtime limit. The
[experiment playbook](experiment-playbook.md) explains those gates.
