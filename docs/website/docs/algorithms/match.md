---
title: Match prediction
description: Compare LZ77 copy tokens with the project’s hashed next-byte match model.
---

# Match prediction

[LZ77](lz77.md) writes a copy instruction when a repeated sequence appears. The `match` codec takes a different route: it uses a recent matching sequence to **predict the next byte**, then arithmetic-codes that byte. If the guess is wrong, the byte is still encoded; the archive just spends more bits.

The `MatchModel` in [`src/ppm_match_mix.rs`](https://github.com/bbondy/hutter/blob/main/src/ppm_match_mix.rs) hashes a four-byte **suffix**—the last four bytes already seen—to find earlier occurrences. A **hash** is a compact lookup key computed from those bytes, used to find likely earlier positions without scanning every position. The model retains up to eight candidates per hash within a 32 KiB window. For each candidate, the byte that followed the previous match becomes a possible next byte. Longer and nearer matches receive more weight. An escape path allows any of the 256 values, including bytes that no match predicted.

Suppose the bytes so far are `abcdXabcd`. The last four bytes are `abcd`; an earlier `abcd` was followed by `X`. That earlier continuation gives `X` a useful next-byte prediction. If the actual next byte is `Y`, the predictor was wrong, but decoding is still possible through the escape path. LZ77 would instead have written a copy token for a repeated span. Here the match affects a probability, not a command to copy output.

For this isolated sequence, the earlier `abcd` starts five bytes behind the current suffix and matches all four suffix bytes. `match_weight` gives that candidate a weight of `25`: a base score of `1` for a four-byte match, multiplied by the near-distance factor `25`. The standalone byte-oriented `match` path also reserves escape weight `16`. With only this one candidate, the first arithmetic choice gives predicted `X` weight `25` out of `25 + 16 = 41`, and the escape weight `16` out of `41`. An escape is followed by a uniform choice among all 256 byte values. Later observations can create additional candidates, changing these counts; the example isolates one prediction step.

## `match` and `ppm-match-mix`

`match` writes a `PMAT` archive. New `PMAT` archives carry an `MBY1` marker after the length and arithmetic-code whole bytes using only the match predictor. The decoder also accepts older `PMAT` archives that used a bitwise match-only payload. The marker matters because the four-byte magic alone cannot distinguish those two payload layouts.

`ppm-match-mix` writes `PMM3`. It combines byte-context probabilities with the match predictor, then codes bits. The decoder retains support for older `PMM2` archives, which also mixed direct bit contexts. The current `PMM3` encoder uses byte and match predictions. These format choices are in `compress`, `decompress`, and `ModelConfig` in the same source file.

## Profile the pieces

```sh
cargo run --release -- profile --no-progress data/sample.txt
```

`profile` runs several model configurations and prints elapsed time, nanoseconds per byte, and archive size. It includes bit-only, byte-only, match-only, byte+match, legacy bit+byte+match, and the current combined configuration. Some rows are internal comparisons rather than standalone CLI archive formats; use the normal `compress` command for a codec you intend to keep.

The sample is for learning, not performance conclusions. For a meaningful comparison, use a representative file, rerun timing measurements, and verify a round trip after changes.

**Next:** [WikiMix-5](wikimix5.md), a separate multi-model experiment aimed at structured wiki text.
