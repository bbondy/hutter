---
title: Rust notation used here
description: Enough Rust syntax to read the codec entry points and model updates.
---

# Rust notation used here

You can follow the compression lessons without writing Rust. This page explains the syntax that appears most often when you open a codec module.

**Source code** is the text programmers write; Cargo compiles the `.rs` files into the CLI program. A **function** is a named sequence of operations that can be called from another part of the program. A **variable** names a value. A **type** says what kind of value it is and which operations are allowed. Braces `{ ... }` group code; a semicolon ends a statement.

Consider the function signature used by several codecs:

```rust
pub fn compress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;
    Ok(())
}
```

| Part | Meaning here |
| --- | --- |
| `pub fn compress` | A function other modules may call. `src/codec.rs` calls it. |
| `let mut data = Vec::new()` | Create a mutable variable named `data` holding an empty growable array. |
| `R: Read`, `W: Write` | Any input type that can be read and any output type that can be written. A file or an in-memory buffer can work. |
| `mut` | The function may change this local value as it reads or writes. |
| `io::Result<()>` | Success returns `Ok(())`; failure returns an I/O error. |
| `?` | If an operation failed, return its error immediately. Otherwise continue with its value. |
| `&mut data` | A temporary, mutable reference to the vector so `read_to_end` can append bytes. |

This is a shortened example. The full functions write an archive header and payload; find them in the [source map](map.md). An `io::Result` does not mean the data is always valid: a decoder also returns errors for bad headers or impossible token values.

`Ok(())` is a successful result with no additional value. `Err(...)` is a failure. The `?` after `read_to_end` means “return that error now if reading failed.” This is why a bad archive can stop decoding without silently producing incorrect output.

## Common data types

- `u8` is one unsigned byte. `u16`, `u32`, and `u64` hold larger unsigned integers. A four-byte magic is often declared as `&[u8; 4]`, a reference to exactly four bytes.
- `usize` is a size or index in memory. Archive fields use fixed-size integers such as `u64` so the file format does not depend on the machine’s pointer size.
- `Vec<u8>` is a growable byte array. `&[u8]` is a borrowed view of bytes, called a **slice**. A function can read a slice without owning or copying the bytes.
- `HashMap<Key, Value>` looks up model state by a context key. `VecDeque<u8>` can keep a rolling history while discarding old bytes.
- `.to_le_bytes()` writes an integer as little-endian bytes; `from_le_bytes()` rebuilds it. Both sides must agree on the order.

## Decisions and loops

`Codec` in `src/codec.rs` is an **enum**, a type whose value is one of several named variants such as `Codec::Lz77` or `Codec::BlockHuffman`. A `match` chooses an operation for each variant:

```rust
match self {
    Self::BlockHuffman => block_huffman::compress(input, output),
    Self::Lz77 => lz77::compress(input, output),
}
```

The real `match` has more arms. `Self::Lz77` means the `Lz77` variant of the current enum; `=>` separates a case from its action. The decoder uses a different decision: it compares the first four archive bytes with known magic values.

A `for` loop repeats an operation. In `for &byte in block`, `block` is a slice of bytes, `byte` is each byte value in turn, and `&` in the pattern reads through the reference supplied by iteration. `freqs[byte as usize]` uses that value as an array index; `as usize` converts the byte-sized integer to an index-sized integer.

Some values may be absent. Rust represents that with `Option`: `Some(symbol)` contains a value and `None` does not. A Huffman tree node holds `Option<u8>` because a leaf has a byte symbol, while an internal branch does not. `if let Some(symbol) = node.symbol` acts only in the leaf case. `Result` is different: it represents success or an error, rather than presence or absence.

## Modules and tests

`src/main.rs` declares modules with lines such as `mod lz77;`. That makes `src/lz77.rs` part of the binary. A line like `use crate::codec::Codec;` brings an item from another module into scope. `pub` controls whether another module can access it.

Tests inside a module appear under `#[cfg(test)]`. `cargo test` builds and runs them. A typical codec test compresses a byte vector, decompresses it, and asserts that the restored bytes equal the input.

You can now read [the archive flow](flow.md) and open one codec’s `compress` and `decompress` functions side by side.
