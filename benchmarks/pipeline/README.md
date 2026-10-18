# Full-corpus preprocessing checks

These records verify specific deterministic stages on the official billion-byte
`enwik9`. They do not contain a full compressed submission score or establish
runtime/memory eligibility for the compressor.

- [Native dictionary derivation](20261017-native-dictionary/report.json): the
  native port derives exactly the shipped 520,804-byte dictionary from enwik9
  and the pinned hint file. SHA-256 is
  `0ab9f2d2733003577b53b206791f382fd31b91eff9975041b2173bb5585c5535`.
- [Native upstream order](../article-order/20261017-upstream-order/validation.json):
  census, comment-index and order stages reproduce upstream's full reordered
  main-stream digest and account for all 243,425 page IDs.
- [Rejected full native coder-stream check](20261017-native-stream-rejected/report.json):
  upstream's `TRAIN_MODE=1` tool, adapted with the Mac port, produced 559,634,858
  packed bytes versus the recorded 552,750,198. The unpacked form is also
  6,884,660 bytes larger. Both expected hashes fail. This is a preprocessing
  stream, not a compressed archive. The cause was subsequently located in two
  signed-overflow-dependent XML entity expressions; the failed record is kept.
  The exact driver source and generated patch are saved alongside the failed
  result because this first run used an uncommitted driver. Stage hashes help
  locate the disagreement without modifying this diagnostic record.

- [Native Linux full stream](20261017-linux-stream-v1/report.json): the untouched
  upstream training tool reproduces both reference hashes on Ubuntu x86-64.
- [Corrected Mac full stream](20261017-native-stream-v3/report.json): explicit
  unsigned entity arithmetic restores the identical 555,771,398-byte unpacked
  and 552,750,198-byte packed streams. Its supplemental recipe record verifies
  the driver and patcher against their subsequent signed source commit.

- [Corrected Linux full stream](20261017-linux-stream-v2/report.json): the same
  explicit unsigned arithmetic preserves both upstream reference hashes and all
  recorded intermediate hashes on native Ubuntu x86-64. The saved CI provenance
  links the workflow, source commit and unchanged Linux comparison.

To repeat dictionary derivation after building the native development source:

```sh
clang++ -O2 -std=c++17 -DDICT_DERIVE_MAIN -Ibuild/native-fixture-v3/source/src \
  build/native-fixture-v3/source/src/preprocess/dict_derive.cpp \
  -o build/derive-dictionary
build/derive-dictionary data/enwik9 engines/cmix-neif/dictionary/english.hints \
  build/derived-english.dic
cmp build/derived-english.dic engines/cmix-neif/dictionary/english.dic
```

The saved report records exact absolute commands, corpus/hint/source/compiler and
executable hashes, output hash, log and native source inventory. Its 67.69-second
run and 1,137,393,664-byte peak RSS were measured with other jobs active and are
exploratory. The Mac adapter only replaces the Linux allocator header/trim calls
in this derivation source. It keeps the integer dictionary algorithm.

The full-stream diagnostic can be repeated with:

```sh
python3 scripts/native_stream.py --enwik9 data/enwik9 \
  --native build/native-fixture-v4 --output build/native-stream-check --portable-entities
```

It applies the pinned upstream training patch before the Mac port, changing only
one patch-context include to compose them without fuzzy hunk matching. It stops
after preprocessing and compares both forms with the hashes in upstream's
`training/tf/1_dump/README.md`. A successful build alone does not pass the check.

On native Linux x86-64, omit `--native`. Omitting `--portable-entities` replays the
original upstream arithmetic; it passed with the recorded Linux compiler and
failed with the recorded Mac compiler. The fix is applied automatically in new
development model builds, while `native_stream.py` retains an explicit option
so the original diagnostic remains reproducible.
