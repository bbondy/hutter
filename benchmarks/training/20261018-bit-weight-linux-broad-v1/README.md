# Fixed bit-model weight on a separate 4 MB Linux range

Native Linux x86-64 [workflow run 39096714986](https://github.com/bbondy/hutter/actions/runs/39096714986)
at source commit `4b9f6e37704e00c458eccf3fddd20e33c50dcd93` tested the
previously screen-selected one-pass BF16 weight on the prepared
[4,002,523-byte raw XML range](../20261018-broad-trace-protocol-v1).
The [frozen protocol](../20261018-bit-weight-broad-protocol-v1/protocol.json)
did not permit tuning to this range.

| Payload | Untouched baseline | Fixed trained weight | Change |
| --- | ---: | ---: | ---: |
| Same 3,728,154-byte prepared input | 476,220 B | 475,970 B | **−250 B** |

Both variants restore the complete prepared input and original XML exactly.
Encoder/decoder context counters agree, and candidate counters match the
baseline. Both development binaries are 577,272 bytes. Serial same-host runs
took approximately 804/807 seconds to compress and 808/808 seconds to decode;
hosted-runner time is exploratory. The importer independently checked 29
conditions, including downloaded binary, payload, logs, manifests and raw
official-corpus segment hashes; a wrong parent protocol was rejected. The
[verification record](verification.json), logs and source metadata are retained.

This is the first fixed-model check on a larger, geographically separate
range and a third native Linux payload gain, not a complete release package or
Hutter Prize score. Once this range is used for broader training, it ceases to
be held out for any model trained on it.
