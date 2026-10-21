# Frozen replay of the separate 4 MB trace

After the [paired archive and trace check](../20261021-broad-trace-v1), the
source-verified public trainer loaded the exact shipped 7,386-byte BF16
checkpoint and linked the compressor's deterministic math. It matched **all
9,746,875 live integer probabilities** before any optimizer update. Changing
the first reference probability was rejected at bit zero. The
[report](report.json) binds the accepted trace, checkpoint, trainer binary,
protocol and both logs by SHA-256. The raw 19 MB negative-control probability
file and approximately 940 MB of trace data remain local.

This establishes frozen-inference replay for this development range; it does
not establish online-learning equivalence, a newly trained model or a prize
archive. The [one-pass training protocol](../20261021-broad-train-protocol-v1/protocol.json)
was frozen after this verification and before candidate training.
