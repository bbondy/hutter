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
