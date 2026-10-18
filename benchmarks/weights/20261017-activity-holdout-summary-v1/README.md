# MLP activity: holdout

The complete instrumented fixture archive is byte-identical to the saved
baseline. All original XML is restored, context counts are unchanged and all
activation moments agree between encoder and decoder. The comparison record
is `benchmarks/model-variants/20261017-activity-holdout-v1`.

All 12,218 neurons activate at least once; the minimum per-neuron nonzero rate
across executed layer calls is 1.2931%. The previously rejected 5%
weight-norm removals account for as much as 17.04% of a layer's squared
activation mass. This is diagnostic magnitude, not coding loss or causal value.
Per-layer values and all three old removal maps are represented in `report.json`.

Layers 0–14 have the same call count; the last layer has fewer because the
runtime skips its MLP when a prompt row's output is unread. The frozen protocol
mentioned adaptive-depth skips broadly; these specific layer-count differences
must not be attributed to depth selection without distinguishing that separate
last-layer optimization.

The weighted single-neuron score estimates its isolated squared residual
contribution. Adding scores ignores correlations/cancellation among neurons.
No new candidate is generated. These are reused Mac fixtures, not a full-data
activation audit, universal dead-neuron proof or prize improvement.
