# Native holdout trace preserves the archive

The complete archive equals the uninstrumented baseline by SHA-256. Original
XML restoration and context checks pass. Encoder and decoder emit identical
trace, channel and integer-probability hashes for 2,399,939 model bits. Large
raw files stay local. This verifies the recorder, not the public trainer.

The wrapper still named protocol v1 and rejected the reader's revised hash
after completion. Its log is retained. The v2 comparison authenticates the
historical recipe and verifies that the current rewrite generates exactly
the compiled C++ bytes; only validation of the six-zone enum changed.

The separate public-trainer replay fails at an integer probability despite
these identical live traces; see `../20261017-bitl-replay-holdout-v1`. Training
remains gated off while that discrepancy is diagnosed.
