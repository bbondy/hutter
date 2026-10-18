# RMS-aware dead-neuron feasibility

The upstream conservative dead-neuron test finds zero additional removals.
This audit adds an idealized RMS-normalization constraint using Cauchy–Schwarz
and a per-coordinate quantization allowance. It also finds **zero candidates**.
The smallest bound is 26.51 times its zero-activation threshold; none is close.

The calculation does not certify floating-point normalization or nonfinite
states. No weights were changed. Because even this idealized diagnostic finds
no candidate, implementing a new safe-pruning rule from it has no current payoff.
This does not prove that no neuron is dead on the actual corpus; measured
activation diagnostics answer a different question.
