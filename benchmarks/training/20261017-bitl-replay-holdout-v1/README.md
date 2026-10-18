# Frozen public-trainer replay mismatch

Both live trace comparisons pass archive identity, exact raw restoration and
encoder/decoder trace identity. The public trainer does not yet reproduce every
recorded probability on Mac. The screen first differs at model bit 665,047
(live 47,768; replay 47,767); the disjoint fixture first differs at bit 281,491
(live 59,892; replay 59,893). Indices are zero-based. Each comparison stops on
its first mismatch, so these are not total mismatch counts.

Both deliberately wrong first probabilities are rejected at bit zero. Exact
weights, source, compiler, binary, trace and protocol hashes are retained. No
new weights have been trained: the planned CPU experiment requires both exact
replay checks to pass. These results do not yet distinguish a missing feature,
a floating-point/code-generation difference or another implementation error.
