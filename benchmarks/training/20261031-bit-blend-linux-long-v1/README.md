# Fixed bit blend on a separate four-megabyte Linux range

[Native Linux run 41157031778](https://github.com/bbondy/hutter/actions/runs/41157031778)
measured untouched, prior one-pass and frozen 25% blend bit predictors on the
same 495-page enwik8 range. The [protocol](../20261029-bit-blend-long-protocol-v1/protocol.json)
fixed the complete-page selection, projected upstream order, prepared input
and model hashes before compression. It uses 4,017,614 raw XML bytes and a
3,732,791-byte prepared stream.

| Native Linux payload | Untouched | Prior one-pass | Selected blend |
| --- | ---: | ---: | ---: |
| Same prepared input | 489,618 B | 489,418 B | **489,292 B** |

The blend saves **126 payload bytes versus prior** and 326 versus untouched.
All three restore the exact prepared input and original XML, retain identical
encoder/decoder contexts, and use 577,272-byte development binaries.
The independent [verification record](verification.json) passes 38 checks
covering the corpus, fixture, source, models, binaries, archives, logs and
results. The [comparison report](comparison/report.json) and 41 hashed,
bounded evidence files are retained. The CI artifact keeps the actual binaries
and archives for seven days.

This is the first blend archive trial on this range, which is separate from
the saved 1 MB fixtures and 20 MB training segment. It tests longer-stream
behavior, but enwik8 is part of the known benchmark corpus and the fixture
omits surrounding full-stream state. Its payload sizes are **not full Hutter
Prize submission scores**. A proportional 1 GB extrapolation of the 126-byte
increment is about 31 KB, with no guarantee of linear scaling; that is far
short of the scale needed for a 1% prize gain. Full enwik9 compression and
self-extracting decode remain necessary.
