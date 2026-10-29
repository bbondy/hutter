# Fixed blend on a third native Linux article range

[Native Linux run 40686979434](https://github.com/bbondy/hutter/actions/runs/40686979434)
tested the previously selected 25% BITLSTM blend against the untouched and
prior one-pass models on one host, using the frozen
[protocol](../20261027-bitl-blend-confirmation-protocol-v1/protocol.json).
The fixture contains 150 complete pages, 1,000,794 raw XML bytes and 924,454
prepared bytes from a geographically separate enwik8 range.

| Payload | Untouched | Prior one-pass | Selected blend |
| --- | ---: | ---: | ---: |
| Third range | 126,001 B | 125,905 B | **125,879 B** |

The blend saves **26 payload bytes versus prior** and 122 versus untouched.
All three restore the exact prepared input and original XML, and encoder and
decoder context counts match each other and the untouched control. The
independent [verification record](verification.json) passed 38 checks over
input, source, model, binary, archive, restored output, logs and result hashes.
The [comparison report](comparison/report.json) and bounded evidence are saved;
the CI artifact retains the actual binaries and archives for seven days.

This range was previously used for an unrelated retrieval experiment and a
fixed prior-model check. It supports generalization of the fixed blend but is
**not untouched final validation**. The values are fixture payload bytes, not
full Hutter Prize submission scores. Full enwik9 compression, self-extracting
decode, resources and eligibility remain unmeasured.
