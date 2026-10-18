# Full cached training dump matches the original

The diagnostic mapping patch reproduces the entire upstream 7,117,383,324-byte
row dump and all three 552,750,204-byte zone/match rasters. Every output file was
hashed again and compared with the completed original run, not only its size.
`verification.json` records the comparison and parent report hashes. The
source inventory matches the canonical preparation with exactly the declared
two-file cache rewrite; binary, dictionary, script revision, protocol and logs
were independently checked before saving.

The mapped run took 810.75 seconds with 5,145,264,128 bytes peak RSS. The original
took 2,405.79 seconds with 4,636,557,312 bytes peak RSS. Both ran alongside other
work: this is an observed iteration improvement, not a controlled speedup
estimate. The observed extra resident memory was 508,706,816 bytes.

The full datasets stay local. This is TRAIN_MODE=2 with constant predictions,
not transformer inference or a decodable archive. The cache is confined to a
diagnostic source copy. Production archive equivalence, Linux release timing
and prize memory eligibility are not established by this result. The frozen
protocol and original run remain available, including the late-read profiles.
