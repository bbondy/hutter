# Isolated E1 metadata forecast: first Mac fixture

The [predeclared E1 protocol](../20261018-e1-protocol-v1/protocol.json)
compared the untouched cmix-neif development binary with the pinned
Ex-Girlfriend page-ID/revision-ID forecast alone. The B2 timestamp forecast,
transformer, bit model, other predictor code and weights were unchanged.

| Screen payload | Baseline | E1 | Change |
| --- | ---: | ---: | ---: |
| Same 1 MB raw-XML article range | 119,065 B | 119,052 B | **−13 B** |

Both variants restored the exact prepared input and original XML; their
encoder/decoder contexts match and E1's counts equal the baseline's.
The uncompressed development executable grew from 873,096 to 877,208 bytes
(+4,112 B). This does not yet show a net package gain; compressed release
code and full-stream payload must be measured separately. Mac wall times
include laptop sleep and are unsuitable for a speed claim. The
[report](report.json) retains exact source, assets, binary, payload, context,
log and original-output hashes. The [disjoint trial](../20261021-e1-holdout-v1)
also saves payload bytes; full release accounting remains open.
