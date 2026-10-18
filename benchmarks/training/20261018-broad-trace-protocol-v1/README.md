# Separate four-megabyte training range

The frozen selection takes complete pages beginning at enwik8 byte 20,013,121
and ending at 24,015,644: 4,002,523 original bytes across 416 pages. It is
disjoint from the existing screen and disjoint evaluation fixtures, and avoids
the previously reserved confirmation range near 89 MB. The exact source
selection was committed before trace collection or model training.

`source-manifest.json` records the selected pages and corrected preparation.
`projected-manifest.json` uses their verified full-corpus upstream order,
including 83 redirect-prefix pages. `sample-verification.json` checks the
three prepared variants against their manifest hashes and confirms that each
restores the exact original XML segment. Only the upstream variant is planned
for the training trace.

The raw XML and 3.7 MB prepared files stay local because they are reproducible
from the checksum-verified official enwik8, these manifests and the pinned
preparer. This keeps Git and review fast while retaining exact input identity.
The next gate is an unchanged archive and matching encoder/decoder trace on
this larger sample. Training results, if any, require another frozen recipe
and separate fixture checks.
