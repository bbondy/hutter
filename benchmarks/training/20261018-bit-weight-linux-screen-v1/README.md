# Trained bit predictor saves 136 bytes on native Linux screen

[Workflow run 39095412166](https://github.com/bbondy/hutter/actions/runs/39095412166)
built the fixed one-pass BF16 model and unchanged baseline serially on one
Ubuntu x86-64 host. The baseline payload is 119,067 bytes; the candidate is
118,931 bytes. Both restore the 1,033,597-byte original XML exactly, and all
encoder/decoder context counters match. Development binaries are both 577,272
bytes; packed release components are measured separately.

`verification.json` records 29 independent checks of the downloaded CI
artifact, including its source revision and frozen protocol, source XML
segment, prepared input, archives, binaries, model hash, reports and logs.
It inventories all retained bounded evidence. The exact archives, binaries
and prepared input remain in the downloaded local artifact, with their hashes
committed here.

The [disjoint Linux result](../20261018-bit-weight-linux-holdout-v1) saves 93
bytes under the same gate. Both reused fixtures are small, so neither result
establishes full-corpus compression or a Hutter Prize score.
