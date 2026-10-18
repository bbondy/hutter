# Competitive compressor

Our primary objective is to win the Hutter Prize. The main implementation track
is now `cmix-neif/`; the Rust codecs in `src/` remain experimental references.
Both tracks live in this repository and share the benchmark-history tooling.

For local Apple Silicon experiments, see the
[native Mac port](ports/cmix-neif-macos/README.md). It builds without Docker,
keeps the predictor models, and uses separately identified development results.
It does not replace verification of the pinned Linux submission build.

## Starting point

We imported the complete, unmodified source tree of
[cmix-neif 1.0](https://github.com/marwoelk/cmix-neif-1.0) at
`1c9ea5ed57ec9718bcb681d20b79e81a60b7a728`, including weights, training material,
licenses and attribution. `cmix-neif.upstream.json` records the origin, upstream
artifact expectations and SHA-256/executable bit of every imported file. This is
ordinary vendored source: our subsequent changes can be reviewed and committed
in this repository without needing another fork or a submodule remote.

The [upstream report](cmix-neif/README.md) gives a prize-format total of
95,914,051 bytes. As checked October 17, 2026, the
[benchmark](https://mattmahoney.net/dc/text.html) lists it as pending, not awarded.
Those are upstream measurements; we have not reproduced them yet.

The smaller [ex-girlfriend 1.0](https://github.com/rlanday/ex-girlfriend/releases/tag/v1.0)
derives from cmix-neif and explicitly targets LTCB without claiming prize
eligibility. It is a useful source of candidate improvements, but smallest LTCB
archive is not our selection criterion. The accepted
[fx2-cmix-transformer](https://github.com/astOwOlfo/fx2-cmix-transformer-v1)
remains the fallback/reference if this candidate cannot be reproduced within the
prize constraints. We are selecting a foundation, not declaring a new result.

## Licensing

The original Rust lab and our independent orchestration scripts retain the root
MIT license. Imported code is governed by its own licenses. cmix-neif declares
the combined compressor **GPL-3.0-only**; retain its `LICENSE`, `NOTICE.md`,
`third_party/` texts and per-file notices when changing or redistributing it.
Do not relabel it MIT. A distributed derivative compressor needs the applicable
GPL source and notices; see [license scope](../LICENSE-SCOPE.md).

Upstream [attribution section 7](cmix-neif/training/ATTRIBUTION.md#7-open-points)
documents unresolved provenance/licensing points, including the libdevice
sine/cosine transcription and the particular inherited fxcm_v26 version. The
GPL declaration is not evidence that every upstream question is resolved. Keep
this review visible before publishing a derived submission. Replacing the trig
routine can change decoded weights and arithmetic-coder predictions; it requires
rebuilding and verifying the whole pipeline, not an untested math substitution.

## Reproduction workflow

On any development host:

```sh
make competitive-verify
make competitive-doctor
```

Verification checks the pristine upstream files. After intentional engine edits
it reports the changed files and exits nonzero; this is useful for distinguishing
the reference from a candidate. `doctor` checks platform, CPU flags and tools
without installing software. The current Apple Silicon macOS host cannot run
this Linux x86-64-v3/AVX2/FMA implementation natively. An emulated x86-64 Linux
container is now available for development comparisons; its reference image
contains `comp9` with the expected published SHA-256. The
[parity harness](ports/cmix-neif-parity/README.md) runs article-aware fixtures
against it. Emulated times do not establish prize eligibility, and no native
persistent Linux x86-64 runner has been provisioned for the full measured submission.

Hosted native Ubuntu jobs now reproduce the exact published `comp9` without
Docker. Clang 18 must select the reference GCC 13 development files: extra GCC
14 packages on the hosted image otherwise change the output. The
[controlled build record](../benchmarks/weights/20261017-linux-packages-gcc13-v1/ci-provenance.json)
saves the compiler selection and binary/package checks. Hosted jobs also run
canonical article fixtures; their time limit cannot cover the full long run.

On a suitable Linux x86-64 host, preferably the upstream Ubuntu 24.04 environment:

1. Inspect `cmix-neif/install.sh` and `cmix-neif/environment.txt`. The upstream
   installer uses sudo/apt and tries to reproduce a dated Ubuntu package snapshot;
   it can fall back to current packages. Run it only on the intended build host.
   We do not invoke it automatically.
2. Run `make competitive-doctor`, then
   `make competitive-build COMPETITIVE_OUTPUT=build/competitive/baseline-001`.
   The output directory must be new. The wrapper invokes upstream `build.sh`
   from there, preserves build logs, source hashes, tool/package metadata and
   the resulting `comp9` hash. Compiler flags and PGO inputs are unchanged.
3. Compare the resulting hash to the recorded upstream `comp9` hash. A mismatch
   is not an automatic functional failure, but must be explained before claiming
   an exact reproduction. The full benchmark still needs an exact decode.
4. Download and verify enwik9 (`make enwik9` and `make verify-enwik9`). In a fresh
   compression directory place enwik9 and comp9, then run the upstream invocation
   `./comp9 -e enwik9 archive9`. Preserve the exact options and their size.
5. In a separate empty directory place only the produced `archive9` and run it.
   Compare `enwik9_uncompressed` byte-for-byte and by SHA-256 with official
   enwik9. Record process-tree resource use, disk peak, environment and packaged
   sizes. Use the upstream README's timing and judging instructions.

The build wrapper and native Mac/Linux article-fixture adapters are ready.
Full-run execution and independent SFX validation remain the next integration
step on a persistent Linux runner. The existing Rust CLI adapter
does not understand SFX packaging or upstream specialized preprocessing. Do not
pass it `comp9` and treat the result as comparable. Keep upstream published
numbers separate from locally measured records in `benchmarks/runs/`.

## First experiments after reproduction

The release executable and canonical preprocessing now match the reference.
Preserve these identities while measuring the full-corpus result. The existing
article-fixture adapters preserve model phase boundaries and restore original
XML; their small payloads remain separate from a full prize result. The shipped weights
expect the upstream transformed stream, so changing that representation can
require retraining; not all raw samples are supported by the submitted frontend.

Start with controlled ablations and resource improvements, then evaluate selected
changes from ex-girlfriend or other donors against the complete baseline. Track
incremental total-size gains and time/RAM costs. Keep only combinations that
remain useful together. Improvements must clear the *then-current* 1% hurdle;
running somebody else's release unchanged is only a baseline.
