# Frozen replay matches every live probability

The public trainer, with the compressor's exact deterministic-math source and
its recorded compile flags, matches every live integer probability on this
fixture. A deliberately wrong first probability fails at bit zero. No optimizer
step occurs: this verifies frozen inference and enables the separately frozen
CPU experiment. It does not establish post-thaw online-update equivalence.

The earlier system-math mismatch is retained in the v1 record. Input traces,
weights and live archives are unchanged. See the linked build report and v3
protocol for source, compiler, binary and math-provider provenance.
