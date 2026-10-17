# Native / Linux parity investigation

The first gate passes: native Mac and Linux now initialize the captured LSTM
arrays and indirect-map offsets identically. Full coder compatibility is not
yet established by this result.

The portable RNG reproduces 10,000 consecutive glibc outputs for each of seeds
0, 1, 923, 2147483648 and 4294967295. The Linux build still uses its original
libc RNG. See [golden comparisons](../../../benchmarks/parity/20261017-rng-v1/result.json).

Both platforms produce exactly the same 20,621,872-byte initialization snapshot,
SHA-256 `1b4cb3223570a957f7f0c3a89e829194d4006cf521338cecd8d631f206c473e7`.
This snapshot covers the explicitly instrumented arrays, not every byte of the
process address space. The initialization-only runs finish before dictionary
training; their one-byte output is not a compressed result. See the
[initialization record](../../../benchmarks/parity/20261017-initialization-v1/report.json).

The Linux reference image contains `comp9` with the exact expected upstream hash:
`8b07d85f0a374b55688fd08d1a464222f766efbb5bfefc2bc94d6abb201133d7`.
The development comparison uses a separately rebuilt binary, retaining Linux
x86 kernels, bounded paging and the upstream compiler flag groups. Both sides
add the same article-count parameter and optional diagnostics. LLVM rejects
some old PGO counts where instrumentation changes function control flow.

The input is the same 19-article fixture as the earlier native feasibility run:
117,161 raw bytes / 108,927 phda9-prepared bytes. The prepared SHA-256 is
`41c15fd48e12fa85b936132f95aac51223c9296ba9b297020d9171a39c5f7ea0`.
The full dictionary and transformer weights are retained.

With Linux-compatible initialization, the native encoding produces 15,221 bytes
and 473,488 trace events. This differs from the earlier Darwin-RNG result of
15,205 bytes; the initialization correction is not a compression improvement.
The native encode took 195.61 seconds, including 145.17 seconds of dictionary
pretraining. A much smaller fixture will retain this fixed startup cost.

The full comparison and a native trace-disabled round trip are still running
at this checkpoint. Their outcomes will be appended here. Neither these sample
payloads nor emulated Linux timings establish a full enwik9 score or prize
eligibility. See the [harness instructions](../../../engines/ports/cmix-neif-parity/README.md).

Builds began before the harness commit; records retain the original HEAD and
exact source inventories. The implementation is committed as `3e6e73c`.
