---
title: Course sequence
description: Read the compression ideas in dependency order, then connect them to the Rust implementation.
---

# Course sequence

The course starts with what a file contains and what lossless compression must preserve. It then builds from two simple ideas—shorter codes for common values and references to repeated data—to prediction, context models, and the codecs in this repository. The codebase material is a separate part; no Rust knowledge is needed for the compression chapters.

No compression or information-theory background is assumed. A **byte** and a **bit** are defined in the first part. Fractions and probabilities are introduced before they are used for coding. Rust notation is explained before the source walkthroughs.

| Part | Read in this order | What becomes clear |
| --- | --- | --- |
| 1. Files and the lossless contract | [What compression does](../foundations/what-is-compression.md) → [Bytes and bits](../foundations/bytes-and-bits.md) → [First round trip](../start/quickstart.md) | What the input and output are; what “exactly restored” means; why an archive has overhead. |
| 2. Frequency codes | [Probability and surprise](../foundations/probability.md) → [Prefix codes](../foundations/prefix-codes.md) → [Huffman](../algorithms/huffman.md) | How counts can lead to shorter codes, and how a decoder identifies each byte. |
| 3. Repeated sequences | [LZ77](../algorithms/lz77.md) | How a decoder reconstructs bytes from earlier output rather than from a code tree. |
| 4. Probabilistic coding | [Arithmetic coding](../foundations/arithmetic-coding.md) → [Byte PPM](../algorithms/byte-ppm.md) | How changing predictions become bits and why both sides must update in the same order. |
| 5. More context models | [Bit PPM](../algorithms/bit-ppm.md) → [PPMD and exclusion](../algorithms/ppmd.md) | What changes when the predicted unit is a bit, and what an escape rules out. |
| 6. Combining predictors | [Mixing](../algorithms/mixing.md) → [Match prediction](../algorithms/match.md) → [WikiMix-5](../algorithms/wikimix5.md) → [How the methods fit together](synthesis.md) | How several imperfect models contribute to one decodable prediction, and how all codec families compare. |
| 7. The implementation | [Codebase overview](../codebase/overview.md) → [Rust notation](../codebase/rust-primer.md) → [File flow](../codebase/flow.md) → [LZ77 source](../codebase/lz77-walkthrough.md) → [Huffman source](../codebase/huffman-walkthrough.md) → [Byte PPM source](../codebase/ppm-walkthrough.md) → [Integer arithmetic coder](../codebase/arithmetic-coder.md) → [Other model families](../codebase/model-families.md) | Where data moves, where each algorithm lives, and how encoder and decoder mirror each other. |
| 8. Working on the project | [Archive formats](../codebase/archive-format.md) → [Developer onboarding](../contribute/onboarding.md) → [Experiments and measurement](../contribute/experiments.md) | How formats are identified, what to change, and how to check correctness and size. |

Each concept chapter uses a small example before describing the repository's implementation. The examples are models for understanding, not claims that the Rust codec writes those exact bytes. The [interactive examples](../lab.mdx) are optional visualizations of three ideas; the linked source walkthroughs describe the actual implementation.

For a specific CLI name or unfamiliar term, use the [codec reference](../reference/codecs.md) or [glossary](../reference/glossary.md). For a particular file, use the [source map](../codebase/map.md).
