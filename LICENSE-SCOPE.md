# License scope

The root `LICENSE` (MIT) applies to the original Rust experiment code and our
independent repository tooling. It does **not** replace the licenses of imported
third-party implementations, their assets, or modified versions of their code.

`engines/cmix-neif/` is a complete upstream source snapshot. The upstream combined
program is declared GPL-3.0-only; its own `LICENSE`, `NOTICE.md`,
`training/ATTRIBUTION.md` and `third_party/` notices remain applicable. Changes to
that derivative compressor retain its applicable licensing. Preserve all
upstream notices and provide the corresponding source when distributing it as
required by those terms.

The compressor patch, C++ drivers and overlays in
`engines/ports/cmix-neif-macos/` and `engines/ports/cmix-neif-parity/` are
GPL-3.0-only derivatives. The independent
Python build/benchmark orchestration remains under the root MIT license. SIMDe
is fetched at a pinned revision for native builds and retains its MIT license
and notices in the build directory.

`engines/ports/cmix-neif-metadata-e1/` contains an experimental GPL-3.0-only
patch and headers from Ryan Landay's Ex-Girlfriend 1.0 derivative. Its
[port notice](engines/ports/cmix-neif-metadata-e1/README.md) pins the source and
describes the fixture adaptation. This does not resolve the inherited
provenance questions below.

Read the open points in `engines/cmix-neif/training/ATTRIBUTION.md`, section 7.
Importing the published source does not resolve the upstream authors' stated
provenance/licensing questions. This repository does not claim those questions
have been cleared for a future submission.
