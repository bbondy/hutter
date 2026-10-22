# One-pass training on a separate 4 MB range: screen gate failed

The [predeclared protocol](protocol.json) trained exactly one CPU pass from
the original shipped BITLSTM checkpoint on the verified, separate
9,746,875-model-bit trace, at three fixed learning rates. Each checkpoint
was exported to the same 7,386-byte BF16 format. Selection used the old
screen's frozen replay cost only; no holdout trace or archive was evaluated.

| Rate (millionths) | Screen cost change vs shipped | Screen cost change vs prior screen-trained checkpoint |
| ---: | ---: | ---: |
| 300 | −76.2 B | +71.5 B |
| 1,000 | −98.1 B | +49.6 B |
| 3,000 (selected) | −124.8 B | **+22.9 B** |

The broad-trained candidates improve on the original shipped checkpoint,
but every one is worse on the screen than our existing one-pass checkpoint.
The selected rate fails the protocol's required ≥1-byte improvement over
that prior checkpoint. The holdout and archive gates were therefore not
opened, and none of these weights is promoted. The [report](report.json),
logs and all checkpoint bytes are retained; a later experiment must freeze a
new question rather than silently retuning this result.

This is evidence of transfer/domain mismatch for this small checkpoint,
not proof that broader training cannot help. The older model was itself
trained on the screen used for this comparison, so its screen score has an
in-sample advantage; a future candidate still needs a disjoint archive win.
