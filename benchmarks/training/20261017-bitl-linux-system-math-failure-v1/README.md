# System math fails frozen replay on native Linux

The first [Linux run 39091101840](https://github.com/bbondy/hutter/actions/runs/39091101840)
linked the standalone replay with system math. The screen first differs at
zero-based bit 910 (live 48,873; replay 48,874), and the disjoint fixture at
bit 230 (live 27,378; replay 27,379). Each run stops at its first mismatch;
these are not total mismatch counts. Deliberately wrong first probabilities
were also rejected, so the replay comparator itself was active.

Both archive/trace comparisons and original-byte restoration passed before
replay. `verification.json` inventories the retained logs and reports and
checks the mismatch logs against the reports. The follow-up
[runtime-math run](../20261017-bitl-linux-screen-v1) changed only the replay
math linkage and passed both complete fixtures. These failed records explain
why standalone numerical parity must be verified against the live coder.
