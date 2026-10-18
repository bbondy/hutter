# Disjoint archive also improves with the selected model

The screening-selected BF16 model was fixed before this trial. On the
unchanged disjoint prepared input, replacing only the embedded bit-predictor
weights reduces the native Mac payload from 117,438 to 117,347 bytes
(**91 bytes saved**). The candidate archive SHA-256 is
`71546674385a128e856ee23a00c1d1410b21ca17e9f7ebfe7a698746c71437d6`.

Both variants restore the original 1,005,977-byte XML exactly, and their
encoder/decoder context counters match. The development binaries are both
873,096 bytes. `report.json` holds the binary, input, archive, model, protocol
and log hashes. Metadata, results and logs were independently rehashed after
the run. The locally retained archives and reconstructed inputs stay outside
Git.

The paired screening trial is in `../20261017-bitl-archive-screen-v1`. This
fixture is disjoint from the screen but has appeared in previous research;
it is not an untouched final test. The result warrants native Linux testing,
not an extrapolated full-corpus or prize claim. Concurrent local timings are
exploratory.
