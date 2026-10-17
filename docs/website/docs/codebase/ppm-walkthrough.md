---
title: Read the byte PPM codec
description: Trace one byte through history, contexts, escape events, arithmetic coding, and synchronized updates.
---

# Read the byte PPM codec

Use `ppm-o1` for this walkthrough. **Order 1** means the previous byte is the context for predicting the next byte. The [byte PPM lesson](../algorithms/byte-ppm.md) explains the idea; this page shows where it appears in [`src/byte_ppm.rs`](https://github.com/bbondy/hutter/blob/main/src/byte_ppm.rs). You can leave the arithmetic-coder math until after you understand the model loop.

## 1. Follow the selected variant

`Codec::parse("ppm-o1")` selects `BytePpmO1` in [`src/codec.rs`](https://github.com/bbondy/hutter/blob/main/src/codec.rs). Its compression arm calls `byte_ppm::compress_order1`. That short function calls `compress_with_order(input, output, MAGIC_ORDER1, 1)`. The `1` is the maximum context order; `MAGIC_ORDER1` is `PP11`.

`compress_with_order` reads the input, writes `PP11` and the original byte length, then creates three values:

| Value | Role |
| --- | --- |
| `Model` | Counts which bytes followed each known context; also keeps an order-0 table for fallback. |
| `ArithmeticEncoder` | Converts the model's symbol ranges into the payload bits. |
| `ByteHistory` | Remembers the most recent byte for this order-1 run. |

The matching decoder is `decompress_order1`, which calls `decompress_with_order` with the same magic and order.

## 2. Read the loop in both directions

The encoder loops over input bytes. For each byte it calls `model.encode_symbol`, then `model.observe`, then `history.push`. The decoder loops until it has restored the length from the header. It calls `model.decode_symbol`, appends the result, then calls the same `observe` and `history.push` operations.

```text
encoder: encode symbol → observe symbol → push symbol into history
decoder: decode symbol → observe symbol → push symbol into history
```

`observe` must use the **old history**. When the input is `AB`, observing `B` with history `A` records “`B` followed `A`.” Pushing `B` first would record the wrong context. The decoder knows the same old history at that point, so both sides make the same update.

## 3. See a context appear

For `ABAB`, the order-1 model evolves like this. “Order 0” means counts without looking at a previous byte.

| Byte being coded | History before it | How the model can code it | New observation afterward |
| --- | --- | --- | --- |
| First `A` | Empty | Order-0 escape, then the byte value. | Add `A` to order 0. |
| First `B` | `A` | No `A` context exists yet; order-0 escape, then the byte value. | Record `A → B`; add `B` to order 0. |
| Second `A` | `B` | No `B` context exists yet; use the order-0 count for `A`. | Record `B → A`; update order 0. |
| Second `B` | `A` | The `A` context already contains `B`; use its count. | Update the `A → B` count and order 0. |

An **escape** means “this context cannot code the byte; try a shorter context.” If even order 0 has not seen it, the coder writes the byte using a uniform 256-value fallback. The decoder follows the same escape path, so it knows which range to read next.

### Every arithmetic event for `ABAC`

The encoder does not send the letters directly after the header. It sends a sequence of choices to `ArithmeticEncoder::encode(cum, freq, total)`. Here is the complete **model-side** event sequence for `ppm-o1` on `ABAC`. The counts in each row are those *before* the row's byte is observed.

| Byte | Available context | Arithmetic events in order | Why |
| --- | --- | --- | --- |
| First `A` | Empty order 0 | `(0, 1, 1)` escape; `(65, 1, 256)` uniform `A` | Nothing has been seen. `A` has numeric byte value 65. |
| `B` | Order 0 has `A:1`; no `A` context exists | `(1, 1, 2)` escape; `(66, 1, 256)` uniform `B` | The missing order-1 context is skipped, not escaped. |
| Second `A` | Order 0 has `A:1, B:1`; no `B` context exists | `(0, 1, 4)` for `A` | The order-0 total is four: two symbol counts and escape frequency two. |
| `C` | Context `A` has `B:1`; order 0 has `A:2, B:1` | `(1, 1, 2)` order-1 escape; `(3, 2, 5)` order-0 escape; `(67, 1, 256)` uniform `C` | `C` is new at both levels. |

`cum` is the total frequency of outcomes listed before the chosen outcome, not the number of bytes already processed. `Context` keeps known symbols sorted by byte value and puts the escape after them. For example, just before `C`, order 0 has three symbol counts (`A:2, B:1`) and two distinct symbols, so `escape_freq()` is two: its escape range starts at cumulative frequency three and has width two. The initial `(0, 1, 1)` event consumes the entire range and contributes no information; the uniform `A` choice still has to be coded.

The decoder makes these choices in the same order. At each stage `target(total)` identifies a range and `consume` narrows the arithmetic interval; after it obtains a byte, `observe` updates the tables. The table is **not** a list of literal bytes in the archive: arithmetic coding combines all these choices into a bitstream. The [integer arithmetic-coder chapter](arithmetic-coder.md) explains that conversion.

## 4. Locate the data structures

`ByteHistory::push` keeps only the last `max_order` bytes. `ByteHistory::key` turns the recent bytes into a lookup key. `Model` has an `order0` `Context` and a vector of context maps; `Model::context_for_order` finds the table for a particular history.

`Model::encode_symbol` tries the longest available context first, writes an escape when that table has not seen the byte, and eventually falls back to order 0. `Model::decode_symbol` makes the same choices from the coded stream. `Context` stores sorted `(symbol, count)` entries; its `observe` method adds or increments a count. `ArithmeticEncoder` and `ArithmeticDecoder` turn those counts into matching numeric ranges. Read [arithmetic coding](../foundations/arithmetic-coding.md) when you want to inspect those range calculations.

The neighboring `compress_with_mixer` and `MixedModel` functions implement a different codec, `ppm-byte-mix`. Ignore them on a first pass through `ppm-o1`.

## 5. Tests and round trips

```sh
cargo test byte_ppm
make roundtrip CODEC=ppm-o1 INPUT=data/sample.txt
```

`cargo test byte_ppm` runs this module's tests; the Makefile command checks a sample `ppm-o1` archive. The tests near the bottom of `src/byte_ppm.rs` cover its byte-order variants, binary data, and an empty mixed-model input. After this walkthrough, [archive formats](archive-format.md) explains how `PP11` tells `decompress_auto` which decoder to call; the [source map](map.md) points to the bit-level and mixed-model variants.
