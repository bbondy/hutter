# Initial measurements — 2026-10-17

All 55 recorded trials restored the original size and SHA-256. The three-repeat
confirmation runs also produced identical archives for each codec. 34 Rust tests
passed. This is an exploratory baseline, not a prize result.

Machine: Apple M4 Max, 128 GiB RAM, macOS ARM64; rustc 1.93.1, default release
profile. Original codec source: `98217887abd1abfc99aa0a41a7ae8b4b49e9b425`.
Only CLI size reporting changed before the frozen confirmation run. Most trials
have one repetition; timings include startup and polling overhead. RSS is decimal MB.
The corpus was official SHA-1-verified enwik8; offsets/SHA-256 are in each saved
manifest. No full enwik8 or enwik9 compression was run.

## 1 MB development comparisons

Archive bytes including codec headers, not executable/weight costs. Both slices
start with empty model state.

| Codec | Prefix bytes | Middle bytes | Prefix compress s | Prefix decompress s | Prefix peak RSS MB |
|---|---:|---:|---:|---:|---:|
| ppm-o4 | 311,304 | 316,097 | 0.238 | 0.240 | 20.7 |
| ppm-o6 | 336,134 | 340,276 | 0.350 | 0.350 | 87.0 |
| ppmd | 282,503 | 285,992 | 0.352 | 0.351 | 87.3 |
| ppmd-bit | 282,007 | 285,569 | 2.318 | 2.369 | 96.5 |
| ppm-byte-mix | 345,961 | 354,242 | 7.553 | 7.633 | 98.7 |
| ppm-match-mix | 368,414 | 372,885 | 26.313 | 29.100 | 4223.5 |
| wikimix5 | 1,067,326 | 1,076,199 | 3.175 | 3.181 | 179.8 |
| gzip | 355,791 | 357,851 | 0.037 | 0.005 | 1.7 |
| bzip2 | 281,323 | 284,371 | 0.077 | 0.040 | 8.0 |
| xz | 290,732 | 292,148 | 0.345 | 0.020 | 78.2 |

`ppmd` is the useful fast Rust baseline. `ppmd-bit` saves only 496 bytes on
the prefix at much greater runtime. `wikimix5` expands both slices. The
`ppm-match-mix` memory cost includes updating its disabled bit expert; this is
a specific implementation problem, not evidence that match mixing inherently
requires that memory.

## 10 MB prefix

| Codec | Archive bytes | Bits/byte | Compress s | Decompress s | Peak RSS MB |
|---|---:|---:|---:|---:|---:|
| ppmd | 2,570,465 | 2.0564 | 3.993 | 3.992 | 343.9 |
| ppmd-bit | 2,567,467 | 2.0540 | 27.787 | 28.747 | 359.7 |
| bzip2 | 2,916,026 | 2.3328 | 0.462 | 0.184 | 8.0 |
| xz | 2,720,256 | 2.1762 | 2.780 | 0.128 | 159.4 |

Here both PPMD variants beat xz and bzip2. This reverses the narrow bzip2 lead
on 1 MB and illustrates why a short-sample win is insufficient.

## 100 KB screen of all codecs

| Codec | Archive bytes | Compress s | Peak RSS MB |
|---|---:|---:|---:|
| huffman | 85,978 | 0.129 | 2.0 |
| huffman-o1 | 53,272 | 1.109 | 21.1 |
| lz77 | 87,772 | 0.187 | 1.9 |
| ppm-o1 | 48,319 | 0.020 | 2.0 |
| ppm-o2 | 39,696 | 0.020 | 2.3 |
| ppm | 35,511 | 0.020 | 3.7 |
| ppm-o4 | 35,448 | 0.040 | 6.1 |
| ppm-o5 | 36,934 | 0.039 | 11.6 |
| ppm-o6 | 38,486 | 0.040 | 18.0 |
| ppm-byte-mix | 40,726 | 0.567 | 20.5 |
| ppmd | 32,439 | 0.073 | 14.0 |
| ppmd-bit | 32,393 | 0.238 | 19.4 |
| ppmd-mix | 93,880 | 3.013 | 709.5 |
| ppm-bit | 55,778 | 0.132 | 2.5 |
| ppm-bit-o16 | 56,164 | 0.242 | 9.7 |
| ppm-bit-o32 | 108,387 | 0.664 | 155.4 |
| ppm-bit-o64 | 136,594 | 2.824 | 1416.2 |
| ppm-bit-mix | 110,076 | 6.041 | 1421.9 |
| ppm-mix | 97,833 | 4.006 | 721.6 |
| match | 53,964 | 0.020 | 5.9 |
| ppm-match-mix | 38,790 | 2.190 | 727.8 |
| wikimix5 | 111,827 | 0.289 | 33.4 |

## Saved evidence

- [Screen](../../../benchmarks/runs/20261017-screen/results.jsonl)
- [Development](../../../benchmarks/runs/20261017-development/results.jsonl)
- [Promotion](../../../benchmarks/runs/20261017-promotion/results.jsonl)
- [Confirmation](../../../benchmarks/runs/20261017-confirmation/results.jsonl)

Each directory contains original metadata and a sample manifest. Use
`python3 scripts/benchmark_history.py list` and `compare` for subsequent runs.
Large archives/logs remain in the original working tree's ignored `build/bench-*`
directories; Git retains measurements and provenance, not those large artifacts.
The abandoned first confirmation run overlapped a rebuild and is deliberately
excluded; the saved confirmation used an immutable executable snapshot.
