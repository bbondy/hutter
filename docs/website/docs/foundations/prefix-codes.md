---
title: Prefix codes
description: Build a tiny Huffman code and see why a decoder can split a bitstream unambiguously.
---

# Prefix codes

Suppose the input is `AAAABBCD`. Its byte counts are `A:4`, `B:2`, `C:1`, `D:1`. The input has eight bytes, or `8 × 8 = 64` bits before any archive structure. Because `A` occurs more often, it is useful to give `A` a shorter code than the others.

A code could give frequent values shorter bit strings:

| Byte | Count | Code | Bits used |
| --- | ---: | --- | ---: |
| `A` | 4 | `0` | 4 |
| `B` | 2 | `10` | 4 |
| `C` | 1 | `110` | 3 |
| `D` | 1 | `111` | 3 |

The data takes `4 + 4 + 3 + 3 = 14` bits with this toy code. Concatenating the codewords in input order gives `00001010110111`. That is not a complete archive: the decoder also needs to know this code or how to rebuild it, and 14 bits occupy two full bytes when stored.

This is a **prefix-free** code: no complete codeword is the beginning of another. A decoder can read a `0` and immediately output `A`. If it sees `10`, it outputs `B`; if it sees `11`, it reads one more bit to choose `C` or `D`. For example, the first four `0` bits of the stream become four `A` bytes, and the next `10` becomes `B`.

## Where the code comes from

A **Huffman tree** is built by repeatedly joining the two least frequent items. For these counts:

```text
C (1) + D (1) → node CD (2)
B (2) + CD (2) → node BCD (4)
A (4) + BCD (4) → root (8)
```

The number in parentheses is a frequency. Put `A` on the root's left branch and the `BCD` node on its right; within that node put `B` on the left and `CD` on the right. Label every left edge `0` and every right edge `1`. Following the path from root to a byte gives the codes in the table: `A=0`, `B=10`, `C=110`, `D=111`. A byte appears only at a **leaf**, a node with no children, so no complete byte path can be a prefix of another.

Other tie choices can produce different but equally valid trees. The encoder and decoder must make the *same* choices. For fixed counts, Huffman gives a shortest average length among codes that assign one prefix-free bit string to each symbol. That does not include the cost of a header or model.

## How the decoder knows when to stop

Fourteen data bits require 16 stored bit positions, leaving two padding bits. If both padding bits are `0`, this toy decoder would read them as two extra `A`s unless it knew when the original input ended. A header can store the original length, and an archive format must tell the decoder how to recover the code tree.

The real [block Huffman](../algorithms/huffman.md) codec starts with a count of one for each of 256 byte values. It builds its first tree from those shared counts, then updates counts after each block. It does **not** simply count the complete input and store the example tree above. The toy code illustrates the rule; the source shows the actual protocol.

The prefix condition is necessary. If `A=0` and `B=01`, a decoder seeing the first `0` cannot know whether that is a complete `A` or the start of `B`. No amount of frequency information resolves that ambiguity without another delimiter or rule.

**Next:** [Arithmetic coding](arithmetic-coding.md), which represents a whole sequence rather than assigning each symbol its own codeword.
