---
title: Developer onboarding
description: Set up the Rust repo, find a codec, make a safe change, and verify it.
---

# Developer onboarding

The project is a Rust command-line experiment. You can contribute without downloading a gigabyte of Wikipedia data. Start with the tracked sample, learn one codec end to end, and keep encode/decode changes synchronized. If the code syntax is new to you, read [Rust notation used here](../codebase/rust-primer.md).

## Set up a checkout

```sh
git clone https://github.com/bbondy/hutter.git
cd hutter
cargo --version
cargo test
cargo build --release
make roundtrip CODEC=huffman
```

Install Rust through [rustup](https://www.rust-lang.org/tools/install) if `cargo` is missing. The crate uses Rust edition 2024 and has no external Rust dependencies. `make` and `cmp` are used by the convenience targets; direct `cargo` commands work without `make`.

## Find the right edit point

1. Use the [codebase overview](../codebase/overview.md) to locate the CLI, dispatch, and codec modules; choose a codec from the [reference table](../reference/codecs.md).
2. Open its source file and read `compress` and `decompress` together.
3. Find the model initialization and the exact point where a byte or bit is observed.
4. If you are adding a new codec name, edit `Codec::parse`, `Codec::compress`, and `decompress_auto` in `src/codec.rs`, plus the CLI usage in `src/cli.rs`.
5. If the archive layout changes, give it a new magic or a versioned marker. Preserve existing decode behavior when practical.

Every decoder reads data it did not generate itself. Check invalid headers, truncated lengths, impossible back-references, and output size limits when you touch parsing. A round trip proves that your own encoder and decoder agree; malformed-input tests cover a different risk.

For model changes, the [byte PPM source walkthrough](../codebase/ppm-walkthrough.md) shows the basic predict/observe order; [other model families](../codebase/model-families.md) locates the later predictors; and [the integer arithmetic coder](../codebase/arithmetic-coder.md) explains the range math shared by several formats. These pages can be read after the algorithm lessons without adding difficulty to the introductory chapters.

## Verification loop

```sh
cargo fmt --check
cargo test
make roundtrip CODEC=your-codec-name
```

For an existing codec, replace `your-codec-name` with its CLI name. Include empty input, one byte, repeated bytes, and non-text bytes in a new codec’s tests. A round trip should compare **bytes**, not decoded text. If you change a predictor or arithmetic math, test both compression and decompression because they can diverge silently.

## The website itself

This guide lives in `docs/website` and uses Docusaurus, like the Brave Bot docs site that inspired its structure. To edit it locally:

```sh
cd docs/website
npm ci
npm run start
npm run build
```

The build checks internal links. A GitHub Actions workflow builds the site for GitHub Pages after changes reach `main`. See the [site README](https://github.com/bbondy/hutter/blob/main/docs/website/README.md) for Pages setup.

**Next:** [Design a useful experiment](experiments.md).
