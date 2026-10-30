# Separate four-megabyte blend evaluation range

The [frozen protocol](protocol.json) selects complete pages starting at the
first page after enwik8 byte 60,000,000. The exact segment is
`[60,014,618, 64,032,232)`: 4,017,614 raw XML bytes across 495 pages. It
does not overlap the earlier screen, disjoint, 20 MB training or third-range
fixtures. The original [source manifest](source-manifest.json), projected
[upstream-order manifest](projected-manifest.json) and
[sample verification](sample-verification.json) bind the official corpus,
all pages, prepared input, inverse transformation and script hashes.

The baseline, prior one-pass and selected 25% blend weights were frozen before
any compression of this sample. The native Linux trial uses the same prepared
3,732,791-byte input for all three. Actual archives, original XML restoration,
context counts and resource logs are the next gate. This is a longer fixture
for length scaling, not a full Hutter Prize submission score.
