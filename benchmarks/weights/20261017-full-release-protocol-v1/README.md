# Complete release run protocol

This protocol freezes the reproduced published baseline and the existing
weight-permutation release candidate. It contains **no full-run results**.
Run the baseline first on a persistent native Linux x86-64 host. Candidate
execution is a later confirmation after the bounded checks; it is not a
parameter sweep. The native hosted build artifact is from run 39083970011;
its hashes remain fixed even after that temporary artifact expires.

```sh
python3 scripts/release_full.py \
  --binary build/ci-release-packages-gcc13-v1/release-baseline/comp9 \
  --enwik9 data/enwik9 \
  --protocol benchmarks/weights/20261017-full-release-protocol-v1/protocol.json \
  --role baseline --cpu 0 --output build/full-release-baseline-v1
```

Choose an allowed logical CPU on an otherwise idle host (`taskset -pc $$` shows
the shell's allowed set); `0` is only an example. Both phases inherit affinity
to that one CPU. This does not reserve the core or prevent unrelated work on
its SMT sibling. Run inside a persistent terminal/session with sufficient
uptime: upstream reports roughly 49 hours **per phase**. The frozen 240,000-second
timeout per phase is an operational bound, not the prize time limit.

The harness copies the verified input and binary into a new encoding directory,
then copies only the completed archive to a fresh decoder directory. It runs the
SFX archive without arguments and compares `enwik9_uncompressed` with official
size and SHA-256. The baseline also has to match the published complete archive
hash. Failure, interruption and timeout records survive; no output directory is
overwritten and restored data is retained.

`report.json` records package bytes, hashes, commands and environment. Each
phase retains `phase.json`, `run.log` and GNU `time.log`; the heartbeat updates
once a minute. Sampling once a second measures process-tree RSS and apparent
and allocated regular-file bytes. Disk samples deduplicate hardlinks and include
open unlinked temporary files via `/proc`, because upstream uses `tmpfile()`.

The sample-based stop conditions are 10 GiB RSS, 100 billion apparent file bytes,
or less than 1 GiB free on the work or `/tmp` filesystems. Initial checks require
35 GiB free in the workspace and 3 GiB in `/tmp`. These are operational guards:
sampling can miss peaks and does not enforce a cgroup limit. GNU time's peak
is retained separately and is not a concurrent whole-process-tree peak. The
decoder directory is isolated from encoder assets by convention, not by a
filesystem/network sandbox.

Use the full judging procedure, a recorded Geekbench 5 single-core score and
machine-normalized timing to assess eligibility. A passing harness run proves
the declared bytes/roundtrip conditions; it does not award a prize or certify
all resource and self-containment rules. No persistent host is configured yet.

The manual `release-harness-checks.yml` workflow runs short synthetic tests of
cleanup, failure retention, resource sampling and acceptance accounting. Those
tests are explicitly separate from running the real compressor to completion.

[Native Linux harness checks](../20261017-full-release-harness-checks-v1/report.json)
pass all 58 tests at revision `1104400`, including the Linux-specific check of
open unlinked files and hardlink deduplication. The saved log and workflow
identify exactly which code was checked; this is not a full compressor run.
