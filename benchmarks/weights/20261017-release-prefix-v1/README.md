# Identical release prefixes, with insufficient model coverage

[Native Linux run 39084877868](https://github.com/bbondy/hutter/actions/runs/39084877868)
used the frozen GCC 13 release pair. Both full preparation pipelines matched
the canonical hashes, both compressed dictionaries were 134,912 bytes with
the same reported hash, and the first 1,048,576 emitted coder bytes matched:
`4ac235aebf457e140d25e9f219f14e29db53a1599a890113f3d89baa2f182f80`.

Both runs deliberately stopped after about 597 seconds, before forming a
complete archive. The downloaded prefix bytes were independently compared;
binary, package-report, protocol, source and log hashes were rechecked locally.
Large prepared files and the compressed dictionary are CI-verified reported
hashes, not files supplied by this artifact. See `verification.json`.

**The logs end at 0.60% in the metadata block.** Neither reaches the redirect
or main-text marker. Upstream gates the transformer off through metadata, so
this result does not test the changed MLP weights on ordinary text. It is useful
release/preprocessing evidence but insufficient model coverage. The original
report's `passed` flag means its frozen v1 acceptance conditions passed; it does
not override this limitation.

The [v2 protocol](../20261017-release-prefix-protocol-v2/protocol.json) compares
4 MiB and requires the main-text marker plus more than 2 MiB of later output
within that fixed prefix. The margin exceeds the encoder's 1 MiB output buffer.
The binary pair and prepared streams stay fixed. No complete archive, independent
SFX decoding, full score or resource eligibility is established by either prefix
test. Partial RSS samples and single-run times are retained without a speed claim.
