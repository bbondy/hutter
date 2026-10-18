# Full-input release pair agrees past the main-text boundary

[Native Linux run 39086476933](https://github.com/bbondy/hutter/actions/runs/39086476933)
ran the reproduced published release package and the model-neuron-permuted
package serially after real, checksum-verified `enwik9` preprocessing. Both
produce the same 4,194,304-byte coder prefix (SHA-256
`51f88a5285dc397a7c9cfa966fcf08ddbd1b8415a58c70ab0f56b15af1e19490`)
and identical compressed-dictionary hashes. Each preparation stage matches
the frozen full-corpus reference hash.

Both logs report entry into the main text block when 1,048,581 output bytes
were observed. The prefix extends another 3,145,723 bytes beyond that point,
exceeding the declared 2 MiB margin. This corrects the earlier 1 MiB prefix
check, which stopped inside metadata. Both processes were deliberately stopped
after prefix capture; they produced no complete archive or independent decoder
round trip.

`verification.json` checks the downloaded prefix files, logs, frozen protocol,
package/source identities, stage hashes and phase margin in 18 conditions. The
8 MiB of prefix files remain in the local artifact; their lengths and hashes
are committed. Observed time to capture was about 5,360 and 5,317 seconds;
sampled process-tree peak RSS was about 10.45 billion bytes for each run.
Neither bounded time nor sampled memory certifies full-run resource eligibility.
The permutation's 8,563-byte measured release-component saving remains a lead,
not a full Hutter Prize score.
