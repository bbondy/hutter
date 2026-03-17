# WikiMix-5

`WikiMix-5` is a future mixed-model codec for this repo. It is additive work only: the existing `ppm-o1` through `ppm-o6` codecs stay as they are.

## Codebase mapping

- [`src/ppm.rs`](/Users/brianbondy/projects/bbondy/hutter/src/ppm.rs) remains the byte-context baseline and the source for arithmetic-coding machinery.
- [`src/lz77.rs`](/Users/brianbondy/projects/bbondy/hutter/src/lz77.rs) is the starting point for a probabilistic match model.
- [`src/codec.rs`](/Users/brianbondy/projects/bbondy/hutter/src/codec.rs) is the right place to add `WikiMix-5` later, as a new codec, without touching the current PPM variants.
- [`src/wikimix.rs`](/Users/brianbondy/projects/bbondy/hutter/src/wikimix.rs) now holds the compileable model skeleton.

## Top-level interface

`WikiMix5Model` owns:

- `ByteHistory`
- `BytePpmModel`
- `StructStateModel`
- `WordModel`
- `MatchModel`
- `ClassModel`
- `Mixer`

The intended coding loop is the same synchronized online pattern used by the current PPM code:

1. gather predictions from all submodels,
2. mix them into one next-byte distribution,
3. arithmetic-code the chosen byte,
4. update every submodel with the actual byte.

## Five models

### `BytePpmModel`

- Reuse the current `ppm` ideas: byte contexts, backoff, adaptive counts.
- Stop rebuilding history from the full prefix each symbol.
- Use `ByteHistory` directly.

### `StructStateModel`

- Detect XML tags, wiki links, templates, tables, headings, entities, URLs, numbers, and UTF-8 regions.
- Maintain per-state next-byte counts.
- Give syntax bytes much more context than plain text.

### `WordModel`

- Track recent token-like words and current word prefix.
- Bias predictions for article prose, tag names, and frequent schema words like `title` or `revision`.

### `MatchModel`

- Convert the current LZ idea from hard token output into next-byte prediction from recent matches.
- Start simple, then replace naive scanning with a hashed matcher.

### `ClassModel`

- Handle patterned classes: dates, years, ISBN-like strings, URLs, entities, UTF-8 continuations.
- Predict by character class first, then byte.

## Mixer plan

The placeholder mixer in [`src/wikimix.rs`](/Users/brianbondy/projects/bbondy/hutter/src/wikimix.rs) just picks the strongest weighted candidate. The real version should:

- take one normalized byte distribution from each model,
- combine them with adaptive weights,
- update those weights online using coding loss on the actual byte.

## Implementation order

1. Extract reusable arithmetic coding from [`src/ppm.rs`](/Users/brianbondy/projects/bbondy/hutter/src/ppm.rs).
2. Make `BytePpmModel` real.
3. Add a hashed `MatchModel`.
4. Fill in `StructStateModel`.
5. Fill in `ClassModel`.
6. Add `WordModel` last.
