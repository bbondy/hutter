# Native Linux archive test: selected BITLSTM blend, disjoint

The same frozen model and [workflow run 39870362623](https://github.com/bbondy/hutter/actions/runs/39870362623)
produced the following complete payloads on the disjoint x86-64 fixture:

| Payload | Untouched | Prior one-pass | Selected blend |
| --- | ---: | ---: | ---: |
| Disjoint | 117,426 B | 117,333 B | **117,303 B** |

The blend saves **30 bytes versus prior** and 123 versus untouched. Every
variant restores the exact prepared input and original XML; context counts
agree within encoder/decoder and among all variants. All development binaries
are 577,272 bytes. The [artifact verifier](verification.json) passed 38
independent checks. This confirms a small real archive gain on both native
Linux fixtures, while complete package and full enwik9 score remain open.
