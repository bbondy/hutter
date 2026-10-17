# Hutter Prize

This repo is a workspace for experimenting toward a future Hutter Prize submission in Rust.

It is not competitive yet. The current repo contains several small experimental codecs:

- adaptive block Huffman
- order-1 adaptive block Huffman
- naive LZ77 with literal and back-reference tokens
- byte-level PPM with arithmetic coding
- bit-level PPM with arithmetic coding

There is also an experimental `WikiMix-5` codec with five heuristic predictors:

- `src/wikimix.rs`
- `docs/wikimix5.md`

Codec names in the CLI:

- `huffman`: original block-model Huffman codec, faster and the default
- `huffman-o1`: order-1 Huffman codec, usually slower
- `lz77`: naive LZ77 codec
- `ppm`: order-3 byte-level PPM-style arithmetic coder
- `ppm-bit`: order-3 bit-level PPM-style arithmetic coder
- `ppm-byte-mix`: mixed-order byte-level PPM with adaptive per-order weights
- `ppm-bit-mix`: mixed-order bit-level PPM candidates with adaptive per-order weights
- `ppm-mix`: hybrid bit coder that mixes byte-level and bit-level predictions
- `match`: standalone byte-level match predictor with arithmetic coding
- `ppm-match-mix`: byte+match hybrid that mixes byte-level PPM and match-model predictions

Family note:

- `ppm-o1` through `ppm-o6` are byte-level PPM codecs
- `ppm-bit`, `ppm-bit-o16`, `ppm-bit-o32`, and `ppm-bit-o64` are bit-level PPM codecs
- `ppm-byte-mix` is byte-level mixed-order PPM
- `ppm-mix` uses both byte-level and bit-level models
- `match` isolates the hashed match model on its own and codes whole bytes directly
- `ppm-match-mix` combines the byte-level mixed model with the hashed match model

Their purpose is to give you a clean, testable loop for:

- compress
- decompress
- profile `ppm-match-mix` internals
- verify correctness
- inspect file sizes quickly

## Research plan and reproducible benchmarks

See [the October 2026 assessment and experiment plan](docs/research-plan.md).
Keep `data/sample.txt` as a smoke test only: its 179 bytes cannot rank models.

```sh
make samples
make bench-suite BENCH_OUTPUT=build/screen-001
python3 scripts/benchmark.py data/samples/prefix-1m data/samples/middle-1m \
  --codecs ppmd ppmd-bit ppm-o4 gzip bzip2 xz --output build/dev-001 \
  --record dev-001 --note "Initial development baseline" \
  --manifest data/samples/manifest.json
python3 scripts/benchmark_history.py list
python3 scripts/benchmark_history.py compare dev-001 dev-002
```

The Python standard-library runner executes codecs serially, checks restored size
and SHA-256, and records archive bytes, bits per byte, compression/decompression
wall time and peak RSS, commands, binary hash, commit, and platform. It retains
archives and logs in a new output directory and records failures/timeouts. Use
`--repeats 3` for timing comparisons and archive repeatability checks. The default
120-second timeout is **per phase**; there is no hard memory limit. Use only small
samples for the uncapped high-order bit models. `make bench` remains a quick
compression-only command; use `bench-suite` for verified comparisons.

[Benchmark history](benchmarks/README.md) lives in Git under `benchmarks/runs/`.
Use `--record` to retain small immutable records with experiment notes and corpus
manifests. Large archives/logs remain in `build/`. Comparisons match input hashes
and codec names and exclude failed or nonrepeatable trials. Today's 55 trials
are saved, with a [readable report](docs/benchmarks/2026-10-17/README.md).

`make samples` verifies official enwik8 before generating 100 KB, 1 MB and 10 MB
prefixes, plus two disjoint 1 MB slices, with offsets and checksums in a manifest.
Once enwik9 is present, `python3 scripts/make_samples.py data/enwik9` also creates
nine spread-out regions. Generated corpora stay untracked; preserve manifests
with any published benchmark results. Reuse the same source/manifest within an
experiment and don't compare cold-slice ratios directly with full-stream ratios.

## Current target

Checked October 17, 2026: the [official prize page](https://hutter1.net/prize/index.htm)
lists **100,424,672 total bytes**, fx2-cmix-T (Vladimir Ivanov), as the accepted
record and lists a next target below **99,420,425 bytes**. The old 2024 target in
this README is obsolete. [Newer submissions are pending](https://mattmahoney.net/dc/text.html),
including cmix-neif 1.0 at a reported **95,914,051 total bytes**; submission order
and acceptance can move the threshold. Recheck before any prize claim.

## What the contest actually requires

Use the [detailed rules](https://hutter1.net/prize/hrules.htm), not archive size alone:

- Reproduce the exact billion-byte enwik9, without external information.
- SFX packaging counts compressor plus self-extracting archive. The separate
  decoder relaxation counts compressor + twice the decoder + payload; when one
  executable serves both roles, this becomes twice that executable + payload.
  Required command/compile option lengths also count. Permitted zipped program
  representations may change the final score.
- Each program must meet the machine-normalized time limit `70,000 / T` hours,
  where T is its Geekbench 5 score, and the 10 GB RAM / 100 GB temporary disk
  limits. No GPU at runtime. The headline target is about 50 hours on one core.
- Supply Windows/Linux x86 executables and documented source under an OSI license.
  An ARM macOS benchmark is useful for development but does not establish compliance.

`stats` reports an unpacked development estimate for this repo's shared binary,
not a validated submission score. We have not built a prize submission package.

## Language notes

Recent winning submissions are mostly C++-centric `cmix` derivatives with shell scripts and, in some cases, Python or notebooks for preprocessing.
Rust is not the common language in public Hutter Prize winners, but it is still a reasonable choice for a clean experimental codebase.

## Workspace layout

- `src/main.rs`: top-level entrypoint
- `src/cli.rs`: command-line parsing and usage text
- `src/codec.rs`: codec selection and archive-format dispatch
- `src/hybrid_ppm.rs`: hybrid byte+bit mixed PPM codec
- `src/ppm_match_mix.rs`: standalone byte-level match codec, legacy match-only decoder, and match-augmented hybrid codec
- `src/block_huffman.rs`: original adaptive block-Huffman codec
- `src/adaptive_huffman.rs`: slower order-1 adaptive block-Huffman codec
- `src/lz77.rs`: simple LZ77 codec
- `src/byte_ppm.rs`: byte-level PPM-style arithmetic codec
- `src/ppm.rs`: bit-level PPM-style arithmetic codec
- `data/sample.txt`: tiny sample corpus for smoke tests
- `data/enwik8`: optional 100 MB Hutter corpus for faster iteration
- `data/enwik9`: optional 1 GB Hutter Prize corpus for full-scale benchmarking

## Commands

Build:

```sh
make build
```

Run a round-trip test on the sample file:

```sh
make roundtrip
```

Select a codec explicitly:

```sh
make roundtrip CODEC=huffman
make roundtrip CODEC=huffman-o1
make roundtrip CODEC=lz77
make roundtrip CODEC=ppm-byte-mix
make roundtrip CODEC=ppm-bit
make roundtrip CODEC=ppm-bit-mix
make roundtrip CODEC=ppm-mix
make roundtrip CODEC=match
make roundtrip CODEC=ppm-match-mix
make roundtrip CODEC=wikimix5
```

Run a round-trip with an explicit codec:

```sh
cargo run --release -- compress --codec huffman data/sample.txt build/sample.huf
cargo run --release -- decompress build/sample.huf build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec huffman-o1 data/sample.txt build/sample-o1.huf
cargo run --release -- decompress build/sample-o1.huf build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec lz77 data/sample.txt build/sample.lz77
cargo run --release -- decompress build/sample.lz77 build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-bit data/sample.txt build/sample.ppm
cargo run --release -- decompress build/sample.ppm build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-byte-mix data/sample.txt build/sample.pbmx
cargo run --release -- decompress build/sample.pbmx build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-bit-mix data/sample.txt build/sample.pmix
cargo run --release -- decompress build/sample.pmix build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-mix data/sample.txt build/sample.mix
cargo run --release -- decompress build/sample.mix build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec match data/sample.txt build/sample.match
cargo run --release -- decompress build/sample.match build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec ppm-match-mix data/sample.txt build/sample.pmm2
cargo run --release -- decompress build/sample.pmm2 build/sample.restored
cmp data/sample.txt build/sample.restored

cargo run --release -- compress --codec wikimix5 data/sample.txt build/sample.wmx5
cargo run --release -- decompress build/sample.wmx5 build/sample.restored
cmp data/sample.txt build/sample.restored
```

If `--codec` is omitted, `compress` defaults to `huffman`. `decompress` auto-detects the archive format from the file header, so you do not need to specify the codec when restoring.

The `match` codec writes new `PMAT` archives with a byte-oriented payload marker. The decoder still accepts older `PMAT` archives produced by the previous bitwise match-only implementation.
The `ppm-match-mix` codec now writes `PMM3` archives for the byte+match design. The decoder still accepts older `PMM2` archives produced by the previous bit+byte+match implementation.

Progress bars are shown by default on terminal runs of `compress`, `decompress`, and `stats`. Use `--no-progress` to disable them:

```sh
cargo run --release -- compress --no-progress --codec ppm-match-mix data/sample.txt build/sample.pmm2
cargo run --release -- decompress --no-progress build/sample.pmm2 build/sample.restored
cargo run --release -- stats --no-progress data/sample.txt build/sample.pmm2
```

Profile the internal `ppm-match-mix` model combinations on one input:

```sh
cargo run --release -- profile data/sample.txt
cargo run --release -- profile --no-progress data/enwik8
```

`profile` prints timings and archive sizes for:

- `bit-only`
- `byte-only`
- `match-only`
- `byte+match`
- `legacy bit+byte+match`
- `ppm-match-mix`

It also prints the percentage of time saved versus the current `ppm-match-mix` implementation.

Run the unit tests:

```sh
cargo test
```

Download the official Hutter corpora into `data/` and verify them:

```sh
make enwik8
make enwik9
make corpora
```

`make corpora` downloads and verifies both `enwik8` and `enwik9`. `make data-files` is an alias for the same target.

Run on a larger input:

```sh
make roundtrip INPUT=data/enwik8
make bench INPUT=data/enwik8
make bench INPUT=data/enwik8 CODEC=huffman
make bench INPUT=data/enwik8 CODEC=huffman-o1
make bench INPUT=data/enwik8 CODEC=ppm-byte-mix
make bench INPUT=data/enwik8 CODEC=ppm-bit
make bench INPUT=data/enwik8 CODEC=ppm-bit-mix
make bench INPUT=data/enwik8 CODEC=ppm-mix
make bench INPUT=data/enwik8 CODEC=match
make bench INPUT=data/enwik8 CODEC=ppm-match-mix
make bench INPUT=data/enwik8 CODEC=wikimix5
make roundtrip INPUT=data/enwik8 CODEC=huffman ARCHIVE=build/enwik8.ahf1 RESTORED=build/enwik8.ahf1.restored
make roundtrip INPUT=data/enwik8 CODEC=huffman-o1 ARCHIVE=build/enwik8.ahf1 RESTORED=build/enwik8.ahf1.restored
make roundtrip INPUT=data/enwik8 CODEC=lz77 ARCHIVE=build/enwik8.lz77 RESTORED=build/enwik8.lz77.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-byte-mix ARCHIVE=build/enwik8.pbmx RESTORED=build/enwik8.pbmx.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-bit ARCHIVE=build/enwik8.ppm RESTORED=build/enwik8.ppm.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-bit-mix ARCHIVE=build/enwik8.pmix RESTORED=build/enwik8.pmix.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-mix ARCHIVE=build/enwik8.mix RESTORED=build/enwik8.mix.restored
make roundtrip INPUT=data/enwik8 CODEC=match ARCHIVE=build/enwik8.match RESTORED=build/enwik8.match.restored
make roundtrip INPUT=data/enwik8 CODEC=ppm-match-mix ARCHIVE=build/enwik8.pmm2 RESTORED=build/enwik8.pmm2.restored
make roundtrip INPUT=data/enwik8 CODEC=wikimix5 ARCHIVE=build/enwik8.wmx5 RESTORED=build/enwik8.wmx5.restored

make roundtrip INPUT=data/enwik9
make bench INPUT=data/enwik9
make bench INPUT=data/enwik9 CODEC=huffman
make bench INPUT=data/enwik9 CODEC=huffman-o1
make bench INPUT=data/enwik9 CODEC=ppm-byte-mix
make bench INPUT=data/enwik9 CODEC=ppm-bit
make bench INPUT=data/enwik9 CODEC=ppm-bit-mix
make bench INPUT=data/enwik9 CODEC=ppm-mix
make bench INPUT=data/enwik9 CODEC=match
make bench INPUT=data/enwik9 CODEC=ppm-match-mix
make bench INPUT=data/enwik9 CODEC=wikimix5
make roundtrip INPUT=data/enwik9 CODEC=huffman ARCHIVE=build/enwik9.ahf1 RESTORED=build/enwik9.ahf1.restored
make roundtrip INPUT=data/enwik9 CODEC=huffman-o1 ARCHIVE=build/enwik9.ahf1 RESTORED=build/enwik9.ahf1.restored
make roundtrip INPUT=data/enwik9 CODEC=lz77 ARCHIVE=build/enwik9.lz77 RESTORED=build/enwik9.lz77.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-byte-mix ARCHIVE=build/enwik9.pbmx RESTORED=build/enwik9.pbmx.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-bit ARCHIVE=build/enwik9.ppm RESTORED=build/enwik9.ppm.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-bit-mix ARCHIVE=build/enwik9.pmix RESTORED=build/enwik9.pmix.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-mix ARCHIVE=build/enwik9.mix RESTORED=build/enwik9.mix.restored
make roundtrip INPUT=data/enwik9 CODEC=match ARCHIVE=build/enwik9.match RESTORED=build/enwik9.match.restored
make roundtrip INPUT=data/enwik9 CODEC=ppm-match-mix ARCHIVE=build/enwik9.pmm2 RESTORED=build/enwik9.pmm2.restored
make roundtrip INPUT=data/enwik9 CODEC=wikimix5 ARCHIVE=build/enwik9.wmx5 RESTORED=build/enwik9.wmx5.restored
```

## Sources

- Official prize page: https://prize.hutter1.net/
- Official rules: https://prize.hutter1.net/hrules.htm
- Official FAQ: https://www.hutter1.net/prize/hfaq.htm
- 2024 winning repo: https://github.com/kaitz/fx2-cmix
- 2021 winning repo: https://github.com/amargaritov/starlit
