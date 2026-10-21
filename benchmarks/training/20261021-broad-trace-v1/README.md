# Broad 4 MB BITLSTM trace

The [frozen comparison protocol](protocol.json) paired the unchanged native
Mac compressor with read-only BITLSTM tracing on 416 complete pages from a
separate enwik8 range. Both produced the **same 476,220-byte payload and
SHA-256**, restored the exact 3,728,154 prepared bytes and 4,002,523
original XML bytes, and matched all context counters. The tracer's encoder
and decoder independently produced identical 9,746,875-bit records,
1,218,360 channel records and integer-probability hashes. The trace remains
below its declared 16-million-model-bit bound.

The [report](report.json) preserves file sizes, hashes, build provenance,
context counts and restoration evidence; approximately 940 MB of raw trace,
channel and probability data remain local for replay/training. Laptop sleep
contaminated wall-clock timings. This experiment validates a training input,
not new weights or a smaller archive. Frozen-probability replay is the next
gate, followed by screen selection and one disjoint check of any checkpoint.
