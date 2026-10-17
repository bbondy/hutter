# Native Apple Silicon feasibility

cmix-neif runs natively on this Apple M4 Max without Docker or Rosetta after a
development portability patch. A complete encode/decode/preprocessing-inverse
chain restored all 117,161 original Wikipedia bytes exactly. This establishes
a local development route, **not equivalence to the submitted Linux build**.

The code and commands are in the [native port guide](../../../engines/ports/cmix-neif-macos/README.md).
The upstream snapshot remains byte-for-byte unchanged. The native patch retains
the transformer, supplied weights, online models, model capacities and
dictionary pretraining. It adapts SIMD, OS interfaces, the PPM memory backing
and an explicit small-corpus article count.

## Verified first result

[Persistent record](../../../benchmarks/runs/20261017-native-pages/record.json),
[measurements](../../../benchmarks/runs/20261017-native-pages/results.jsonl),
[sample manifest](../../../benchmarks/runs/20261017-native-pages/samples.json),
[validation and logs](../../../benchmarks/runs/20261017-native-pages/validation.json).

| Measurement | Result |
|---|---:|
| Original enwik8 articles | 19 |
| Original bytes | 117,161 |
| phda9-prepared input bytes | 108,927 |
| Compressed payload bytes | 15,205 |
| Compress wall time | 185.60 s |
| Decompress wall time | 188.59 s |
| Peak compress RSS | 5,762,269,184 B |
| Peak decompress RSS | 5,754,765,312 B |
| Native compressor build, excluding dependency fetch/checks/helper | 7.01 s |
| Native executable size | 869,832 B |
| Exact prepared-stream restoration | Pass |
| Exact original-XML restoration after phda9 inverse | Pass |

One exploratory trial; repeatability and controlled timing comparisons are not
established. The 15,205 bytes exclude the external dictionary, weights and
executable, so this is neither a standalone archive size nor a Hutter score.
The model sees 58,917 bytes after its additional dictionary/metadata transforms.
SIMD cancellation and rounding probes passed under both strict and fast FP
compilation. Seven existing Python tests passed.

## Sample design and obstacles

Raw slices are unsuitable for the release's predictor. It expects transformed
metadata and hardcodes 243,425 article records. We preserved the format checks
and added `--native-pages N`, supplied identically to encoder and decoder from
the sample manifest. The default stays at 243,425. This extra development
parameter is not stored in the payload.

Two failed configurations are retained, including diagnostics:

- [Inherited profiling fixture](../../../benchmarks/runs/20261017-native-profile/diagnostics.json):
  rejected by the current release metadata parser.
- [Prepared sample with the original full-corpus count](../../../benchmarks/runs/20261017-native-prepared/diagnostics.json):
  preprocessing reversed correctly, but the coder rejected the incomplete
  metadata block. This motivated the article-count option.

Create samples from complete articles and apply phda9 before dictionary coding.
The 100 KB target selected enwik8 offsets 1,404 through 118,565 (exclusive end).
A 1 MB target also passed preprocessing/inverse checks: 172 articles,
1,033,597 original bytes and 950,787 prepared bytes. Its compression was not run.
Samples keep original article order and omit the full-corpus census,
comment-index and article-reordering stages.

Dictionary pretraining alone cost 136.68 s on compression and 139.04 s on
decompression. Tiny files do not remove that fixed cost. Use this article-aware
fixture for correctness/screening and larger samples for promotion.

## Next decision

Use the native port for local experiments, with its own baseline records.
[Issue #10](https://github.com/bbondy/hutter/issues/10) tracks the required Linux
comparison: libc `rand()` currently initializes the LSTM and indirect maps
differently on Darwin and glibc, even with the same seed. Reproduce the Linux
sequence explicitly, compare initial state and per-byte probabilities, and
cross-decode identical prepared fixtures before claiming equivalence.

Floating-point/code-generation differences also remain unverified. The Mac
port's anonymous 14,000 MiB PPM heap has no Linux resident-memory clamp; small
sample RSS does not establish full-corpus prize eligibility. The self-extractor,
full enwik9 score, timing and memory verification remain in
[issue #1](https://github.com/bbondy/hutter/issues/1).
