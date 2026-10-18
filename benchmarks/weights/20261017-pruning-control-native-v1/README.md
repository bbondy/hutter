# Pruning width control: native Mac

All three frozen pruning geometries pass 16,384 synthetic MLP block cases each
(49,152 total). Retained quantized activations match after index mapping, removed
rows are zero, and sparse/dense residual outputs are bit-identical between the
full-width masked model and physically pruned model. The unmasked original is
rejected with a nonzero-count mismatch for each candidate (exit 4).

The masked control changes only the removed up rows to zero and retains all
original tensor shapes, scales and down columns. The probe uses the recorded
native build's actual kernels and per-file compiler flags. This controls for
width packing, odd tails and both down-projection routes on these inputs.

It does not prove equality for every possible input or test the entire
transformer/coder. It does not make pruning equivalent to the original model.
The six measured payload regressions remain rejected. These checks reduce the
likelihood that the observed losses are simply a width-handling kernel bug;
activation-aware selection, compensation or retraining are more useful next
hypotheses than another blind weight-norm sweep.

Large masked containers, objects and the probe executable remain local;
protocol, exact hashes, index maps, commands and all success/failure logs are
preserved here. This is Mac evidence, not a native Linux result or prize score.
