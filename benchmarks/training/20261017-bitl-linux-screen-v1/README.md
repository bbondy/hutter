# Native Linux screen trace and frozen replay pass

[CI run 39091795827](https://github.com/bbondy/hutter/actions/runs/39091795827)
at source `f8200a0` preserves the original 119,067-byte fixture archive and
restores the source XML. The encoder and decoder traces match. The public
trainer, linked with the compressor's deterministic math and frozen before
online updating, matches all 2,418,059 live integer probabilities. A changed
first probability is rejected.

`verification.json` records 31 independently checked conditions, including
the archived payload and restored prepared-input hashes, source XML segment,
protocol and manifest hashes, replay and negative-control logs, and checkpoint
audit. It inventories every retained JSON and log file. Raw traces, binaries,
prepared inputs and archives remain in the downloaded local CI artifact; their
hashes are retained here. The [disjoint record](../20261017-bitl-linux-holdout-v1)
passes the same gate. This verifies frozen inference, not online updates or a
trained-model compression gain.
