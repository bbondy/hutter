# Fixed bit-model weight on a third Mac range

The [frozen protocol](protocol.json) tested the previously screen-selected
7,386-byte BF16 checkpoint once on a geographically separate enwik8 range:
150 complete pages, 1,000,794 raw XML bytes and 924,454 prepared bytes.
This range had already been used for an unrelated retrieval comparison, so it
is a supporting generalization check, not untouched final validation.

| Native Mac payload | Baseline | Fixed trained weight | Change |
| --- | ---: | ---: | ---: |
| Same prepared input | 125,991 B | 125,896 B | **−95 B** |

Both builds restore the exact prepared input and original XML. Their
encoder/decoder context counters match and the candidate's counters match the
baseline. Both development binaries are 873,096 bytes. Concurrent one-shot
timings were about 619 seconds per compression and 649 seconds per decode;
they are exploratory, not controlled speed estimates. The [report](report.json)
preserves source/binary, input, assets, payload, log and original-output hashes.

This third-range gain supports the fixed one-pass model beyond the first two
fixtures. It is still a payload-only development result, not a full-stream
package or Hutter Prize score. The protocol disallows retuning to this range.
