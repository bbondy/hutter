---
title: How to use this guide
description: A suggested route for new learners and a faster route for developers.
---

# How to use this guide

Each algorithm page starts with an example, explains the idea, and then identifies its implementation in this repository. The [course sequence](../course/path.md) puts the chapters in dependency order. You can read from the beginning without knowing compression vocabulary.

## If you are new to compression

1. Read [what compression does](../foundations/what-is-compression.md) and [bytes and bits](../foundations/bytes-and-bits.md). These define the input and the goal.
2. [Run a round trip](quickstart.md). The commands and their arguments are explained there.
3. View the [interactive examples](../lab.mdx). They are deliberately smaller than the Rust codecs.
4. Read [probability](../foundations/probability.md), [prefix codes](../foundations/prefix-codes.md), and [arithmetic coding](../foundations/arithmetic-coding.md).
5. Walk through [Huffman](../algorithms/huffman.md) and [LZ77](../algorithms/lz77.md) before PPM.

You do not need to memorize a formula. When a page mentions a **context**, think “the bytes or bits already seen.” When it mentions a **model**, think “a rule that estimates what comes next.” The [glossary](../reference/glossary.md) is always available.

## If you want to change code

The [Codebase section](../codebase/overview.md) is separate from the foundations, so you can skip it until you want to read or change Rust. Begin with the repository layout, then use [Rust notation used here](../codebase/rust-primer.md) if the syntax is unfamiliar. Follow the [archive flow](../codebase/flow.md) and one worked example: [LZ77](../codebase/lz77-walkthrough.md), [block Huffman](../codebase/huffman-walkthrough.md), or [byte PPM](../codebase/ppm-walkthrough.md). The [source map](../codebase/map.md) and [onboarding](../contribute/onboarding.md) help with your own change.

## If you want to compare algorithms

The [codec reference](../reference/codecs.md) lists every CLI name and its source module. The [experiments guide](../contribute/experiments.md) explains fair comparisons, round trips, `stats`, `profile`, and the two optional Wikipedia corpora. The sample file is for learning correctness, not for ranking codecs.

<details>
<summary>What does “order” mean?</summary>

An order-1 **byte** model looks at the previous one byte; order-3 looks at the previous three bytes. An order-8 **bit** model looks at the previous eight bits. These are different units. The CLI names `ppm-oN` use bytes, while `ppm-bit-oN` use bits.

</details>
