# Screen archive improves with the trained bit predictor

The protocol selected and hashed the 7,386-byte BF16 model before either
archive trial. On the unchanged prepared screening input, replacing only the
embedded bit-predictor weights reduces the native Mac payload from 119,065 to
118,917 bytes (**148 bytes saved**). The candidate archive SHA-256 is
`2887891d9065d824026eb7a1eaceb38c8547b46be851b6162925b4bae8b2c02b`.

Both variants restore the original 1,006,099-byte XML exactly, and their
encoder/decoder context counters match. The development binaries are both
873,096 bytes; this is not packed release-size accounting. `report.json` holds
the binary, input, archive, model, protocol and log hashes. Metadata, results
and logs were independently rehashed after the run. The locally retained
archives and reconstructed inputs remain outside Git.

The paired disjoint trial is in `../20261017-bitl-archive-holdout-v1`. These
reused small fixtures screen a model hypothesis; they do not establish a
full-corpus Hutter Prize gain. Native Linux, packed package size and a longer
stream are the next gates. Concurrent local timings are exploratory.
