use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"AHF1";
const DEFAULT_BLOCK_SIZE: usize = 64 * 1024;
const SYMBOLS: usize = 256;
const MAX_FREQUENCY_SUM: u64 = 1 << 20;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Code {
    bits: u64,
    len: u8,
}

#[derive(Clone, Debug)]
struct Node {
    left: Option<usize>,
    right: Option<usize>,
    symbol: Option<u8>,
}

pub fn compress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(MAGIC)?;
    output.write_all(&(DEFAULT_BLOCK_SIZE as u32).to_le_bytes())?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut model = Model::new();
    let mut offset = 0usize;

    while offset < data.len() {
        let end = (offset + DEFAULT_BLOCK_SIZE).min(data.len());
        let block = &data[offset..end];
        let codes = build_codes(&model.freqs)?;
        let encoded = encode_block(block, &codes)?;

        output.write_all(&(block.len() as u32).to_le_bytes())?;
        output.write_all(&(encoded.len() as u32).to_le_bytes())?;
        output.write_all(&encoded)?;

        model.observe(block);
        offset = end;
    }

    Ok(())
}

pub fn decompress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut magic = [0u8; 4];
    input.read_exact(&mut magic)?;
    if &magic != MAGIC {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid archive magic",
        ));
    }

    let block_size = read_u32(&mut input)? as usize;
    if block_size == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid block size",
        ));
    }
    let original_size = read_u64(&mut input)? as usize;

    let mut model = Model::new();
    let mut restored = 0usize;

    while restored < original_size {
        let block_len = read_u32(&mut input)? as usize;
        let payload_len = read_u32(&mut input)? as usize;
        if block_len == 0 || block_len > block_size || restored + block_len > original_size {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid block length",
            ));
        }

        let mut payload = vec![0u8; payload_len];
        input.read_exact(&mut payload)?;

        let tree = build_tree(&model.freqs)?;
        let block = decode_block(&payload, block_len, &tree)?;
        output.write_all(&block)?;
        model.observe(&block);
        restored += block_len;
    }

    Ok(())
}

struct Model {
    freqs: [u32; SYMBOLS],
}

impl Model {
    fn new() -> Self {
        Self {
            freqs: [1; SYMBOLS],
        }
    }

    fn observe(&mut self, block: &[u8]) {
        for &byte in block {
            self.freqs[byte as usize] = self.freqs[byte as usize].saturating_add(1);
        }

        let sum: u64 = self.freqs.iter().map(|&v| u64::from(v)).sum();
        if sum > MAX_FREQUENCY_SUM {
            for freq in &mut self.freqs {
                *freq = (*freq).div_ceil(2).max(1);
            }
        }
    }
}

fn encode_block(block: &[u8], codes: &[Code; SYMBOLS]) -> io::Result<Vec<u8>> {
    let mut writer = BitWriter::default();
    for &byte in block {
        let code = codes[byte as usize];
        writer.write_bits(code.bits, code.len)?;
    }
    Ok(writer.finish())
}

fn decode_block(payload: &[u8], output_len: usize, tree: &DecodeTree) -> io::Result<Vec<u8>> {
    let mut reader = BitReader::new(payload);
    let mut output = Vec::with_capacity(output_len);

    while output.len() < output_len {
        let mut node_idx = tree.root;
        loop {
            let node = &tree.nodes[node_idx];
            if let Some(symbol) = node.symbol {
                output.push(symbol);
                break;
            }

            let bit = reader.read_bit()?.ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::UnexpectedEof,
                    "ran out of bits while decoding",
                )
            })?;
            node_idx = if bit == 0 {
                node.left.ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "missing left child")
                })?
            } else {
                node.right.ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "missing right child")
                })?
            };
        }
    }

    Ok(output)
}

fn build_codes(freqs: &[u32; SYMBOLS]) -> io::Result<[Code; SYMBOLS]> {
    let tree = build_tree(freqs)?;
    let mut codes = [Code { bits: 0, len: 0 }; SYMBOLS];
    assign_codes(&tree.nodes, tree.root, 0, 0, &mut codes)?;
    Ok(codes)
}

fn assign_codes(
    nodes: &[Node],
    idx: usize,
    bits: u64,
    len: u8,
    codes: &mut [Code; SYMBOLS],
) -> io::Result<()> {
    let node = &nodes[idx];
    if let Some(symbol) = node.symbol {
        codes[symbol as usize] = Code {
            bits,
            len: len.max(1),
        };
        return Ok(());
    }

    let left = node
        .left
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "missing left child"))?;
    let right = node
        .right
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "missing right child"))?;

    if len >= 63 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "code length exceeded u64 capacity",
        ));
    }

    assign_codes(nodes, left, bits << 1, len + 1, codes)?;
    assign_codes(nodes, right, (bits << 1) | 1, len + 1, codes)?;
    Ok(())
}

struct DecodeTree {
    nodes: Vec<Node>,
    root: usize,
}

fn build_tree(freqs: &[u32; SYMBOLS]) -> io::Result<DecodeTree> {
    let mut nodes = Vec::with_capacity(SYMBOLS * 2);
    let mut heap: BinaryHeap<Reverse<(u32, usize, usize)>> = BinaryHeap::new();

    for (symbol, &freq) in freqs.iter().enumerate() {
        let idx = nodes.len();
        nodes.push(Node {
            left: None,
            right: None,
            symbol: Some(symbol as u8),
        });
        heap.push(Reverse((freq, symbol, idx)));
    }

    let mut next_tie = SYMBOLS;
    while heap.len() > 1 {
        let Reverse((w1, _, i1)) = heap.pop().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "failed to build huffman heap")
        })?;
        let Reverse((w2, _, i2)) = heap.pop().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "failed to build huffman heap")
        })?;

        let idx = nodes.len();
        nodes.push(Node {
            left: Some(i1),
            right: Some(i2),
            symbol: None,
        });
        heap.push(Reverse((w1.saturating_add(w2), next_tie, idx)));
        next_tie += 1;
    }

    let Reverse((_, _, root)) = heap
        .pop()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "empty huffman heap"))?;

    Ok(DecodeTree { nodes, root })
}

#[derive(Default)]
struct BitWriter {
    bytes: Vec<u8>,
    current: u8,
    used_bits: u8,
}

impl BitWriter {
    fn write_bits(&mut self, bits: u64, len: u8) -> io::Result<()> {
        if len == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "cannot write zero-length code",
            ));
        }

        for shift in (0..len).rev() {
            let bit = ((bits >> shift) & 1) as u8;
            self.current = (self.current << 1) | bit;
            self.used_bits += 1;
            if self.used_bits == 8 {
                self.bytes.push(self.current);
                self.current = 0;
                self.used_bits = 0;
            }
        }
        Ok(())
    }

    fn finish(mut self) -> Vec<u8> {
        if self.used_bits > 0 {
            self.current <<= 8 - self.used_bits;
            self.bytes.push(self.current);
        }
        self.bytes
    }
}

struct BitReader<'a> {
    bytes: &'a [u8],
    byte_index: usize,
    bit_index: u8,
}

impl<'a> BitReader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self {
            bytes,
            byte_index: 0,
            bit_index: 0,
        }
    }

    fn read_bit(&mut self) -> io::Result<Option<u8>> {
        if self.byte_index >= self.bytes.len() {
            return Ok(None);
        }

        let byte = self.bytes[self.byte_index];
        let bit = (byte >> (7 - self.bit_index)) & 1;
        self.bit_index += 1;
        if self.bit_index == 8 {
            self.bit_index = 0;
            self.byte_index += 1;
        }
        Ok(Some(bit))
    }
}

fn read_u32<R: Read>(input: &mut R) -> io::Result<u32> {
    let mut buf = [0u8; 4];
    input.read_exact(&mut buf)?;
    Ok(u32::from_le_bytes(buf))
}

fn read_u64<R: Read>(input: &mut R) -> io::Result<u64> {
    let mut buf = [0u8; 8];
    input.read_exact(&mut buf)?;
    Ok(u64::from_le_bytes(buf))
}

#[cfg(test)]
mod tests {
    use super::{compress, decompress};

    #[test]
    fn roundtrip_small_text() {
        let input = b"banana bandana banana bandana";
        let mut compressed = Vec::new();
        compress(&input[..], &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    #[test]
    fn roundtrip_binary() {
        let input: Vec<u8> = (0..=255).chain(0..=255).collect();
        let mut compressed = Vec::new();
        compress(&input[..], &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
