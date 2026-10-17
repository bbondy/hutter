# WikiMix-5 status

`wikimix5` is an implemented experimental byte coder, not a design skeleton.
See [the research plan](research-plan.md) for measured limitations and priorities.

[src/wikimix.rs](../src/wikimix.rs) combines five predictors: byte contexts up to
order six, a syntax state, recent words/current prefix, a four-byte keyed matcher,
and character classes. It arithmetic-codes a candidate or an escape followed by
a uniform byte. All predictors update from already-coded bytes.

The current mixer multiplies raw candidate counts by fixed weights
`[14, 8, 5, 10, 6]`, adds them, and keeps twelve candidates. It neither selects
only one winner nor learns normalized model weights. Individual context models
also discard all but their top two or three symbols. These choices lose useful
probability mass and can make escapes very costly as counts grow.

Before adding more models:

1. Measure each predictor's coding loss and the contribution of each to the mix.
2. Use complete, smoothed distributions or a calibrated escape/backoff path.
3. Compare adaptive linear and logistic mixing with conservative initialization.
4. Bound context tables and match history. The current `window` is not a global
   memory bound: retained data and keys keep growing, and stale positions in
   other buckets are not removed on every byte.
5. Promote only improvements that survive independent slices and longer runs.

The simpler `ppmd` codec is the initial Rust reference. A byte model lives in
[byte_ppm.rs](../src/byte_ppm.rs); [ppm.rs](../src/ppm.rs) contains bit contexts
(orders count bits). Arithmetic-coder consolidation can follow captured archive
fixtures; it should not precede useful compression experiments.
