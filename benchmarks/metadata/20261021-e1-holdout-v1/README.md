# Isolated E1 metadata forecast: disjoint Mac fixture

The same pinned E1-only binary from the [predeclared protocol](../20261018-e1-protocol-v1/protocol.json)
was measured on the disjoint article range after the screen trial. No source,
weight, timestamp, input-order or model parameter was retuned.

| Disjoint payload | Baseline | E1 | Change |
| --- | ---: | ---: | ---: |
| Same 1,005,977-byte raw XML range | 117,438 B | 117,422 B | **−16 B** |

Both archives restore the prepared bytes and original XML exactly. The
encoder/decoder context counters match and the E1 counts equal baseline.
The unpacked development binary remains 4,112 bytes larger than baseline.
Along with the [screen's 13-byte gain](../20261019-e1-screen-v1), this passes
the two-fixture payload gate but does **not** establish a smaller scored
package. Mac wall times include laptop sleep and should not be compared as
speed measurements. The [report](report.json) preserves all result hashes.
