# Native Mac archive test: selected BITLSTM blend, disjoint

The same frozen three-way protocol and selected BF16 model were measured
on the disjoint prepared input, with no retuning after screen selection.

| Payload | Untouched | Prior one-pass | Selected blend |
| --- | ---: | ---: | ---: |
| Disjoint | 117,438 B | 117,347 B | **117,315 B** |

The blend saves **32 bytes versus prior** and 123 versus untouched. Every
variant restores exact original XML and has matching encoder/decoder and
baseline-identical context counts. All development binaries are 873,096
bytes. Laptop sleep contaminates wall time. The [report](report.json)
preserves source and result hashes; this is a fixture payload, not a prize
score or complete release package.
