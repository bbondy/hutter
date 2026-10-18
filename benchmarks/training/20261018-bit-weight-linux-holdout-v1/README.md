# Trained bit predictor saves 93 bytes on native Linux disjoint fixture

[Workflow run 39095412166](https://github.com/bbondy/hutter/actions/runs/39095412166)
built the fixed one-pass BF16 model and unchanged baseline serially on one
Ubuntu x86-64 host. The baseline payload is 117,426 bytes; the candidate is
117,333 bytes. Both restore the 1,005,977-byte original XML exactly, and all
encoder/decoder context counters match. Development binaries are both 577,272
bytes; packed release components are measured separately.

`verification.json` records 29 independent checks of the downloaded CI
artifact, including its published source revision and frozen protocol, source
XML segment, prepared input, archives, binaries, model hash, reports and logs.
It inventories all retained bounded evidence. A deliberately corrupted
candidate archive was rejected before any evidence was saved. The exact
archives, binaries and prepared input remain in the downloaded local artifact,
with their hashes committed here.

The screen Linux job was still running when this record was saved. This is a
small reused-fixture result, not a full-corpus or Hutter Prize score.
