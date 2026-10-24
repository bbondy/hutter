# Metadata forecast experiments

The [frozen E1-only protocol](20261018-e1-protocol-v1/protocol.json) imports
Ryan Landay's GPL-3.0-only page-ID/revision-ID forecast from pinned
Ex-Girlfriend 1.0 into a disposable cmix-neif build. It leaves the separate
B2 timestamp forecast disabled. Both native Mac fixtures restore original
XML and have baseline-identical context counts:

| Fixture | Baseline → E1 payload | Unpacked binary change |
| --- | ---: | ---: |
| [Screen](20261019-e1-screen-v1) | 119,065 → 119,052 B (−13 B) | +4,112 B |
| [Disjoint](20261021-e1-holdout-v1) | 117,438 → 117,422 B (−16 B) | +4,112 B |

The gains are small. The [native Linux release comparison](20261023-e1-release-v1)
finds **+2,094 bytes** of measured components (packed compressor plus
independent decoder prefix). The small fixture savings cannot establish a
net scored win against that cost. Treat E1 as an open full-stream hypothesis,
not a prize improvement. [Issue #18](https://github.com/bbondy/hutter/issues/18)
tracks the separate timestamp forecast and eventual full-stream accounting.
