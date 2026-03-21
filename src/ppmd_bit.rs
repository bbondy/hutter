use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"PDBT";
const MAX_ORDER: usize = 6;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const STATE_BITS: u32 = 32;
const MAX_RANGE: u64 = (1u64 << STATE_BITS) - 1;
const HALF: u64 = 1u64 << (STATE_BITS - 1);
const QUARTER: u64 = HALF >> 1;
const THREE_QUARTERS: u64 = HALF + QUARTER;

pub fn magic() -> &'static [u8; 4] {
    MAGIC
}

pub fn compress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(MAGIC)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut model = BitModel::new();
    let mut encoder = ArithmeticEncoder::new();

    for &byte in &data {
        for bit in ByteBits::new(byte) {
            let p1 = model.bit_probability();
            encode_probability(bit, p1, &mut encoder)?;
            model.observe_bit(bit);
        }
    }

    output.write_all(&encoder.finish()?)?;
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

    let original_size = read_u64(&mut input)? as usize;
    let mut payload = Vec::new();
    input.read_to_end(&mut payload)?;

    let mut model = BitModel::new();
    let mut decoder = ArithmeticDecoder::new(&payload)?;
    let mut restored = ByteCollector::with_capacity(original_size);

    while restored.len() < original_size {
        let p1 = model.bit_probability();
        let bit = decode_probability(p1, &mut decoder)?;
        restored.push(bit)?;
        model.observe_bit(bit);
    }

    output.write_all(restored.finish()?.as_slice())?;
    Ok(())
}

struct BitModel {
    order0: Context,
    contexts: Vec<HashMap<u64, Context>>,
    history: ByteHistory,
    current_byte: u8,
    used_bits: u8,
}

impl BitModel {
    fn new() -> Self {
        Self {
            order0: Context::new(),
            contexts: (0..MAX_ORDER).map(|_| HashMap::new()).collect(),
            history: ByteHistory::new(MAX_ORDER),
            current_byte: 0,
            used_bits: 0,
        }
    }

    fn bit_probability(&self) -> f64 {
        let mut excluded = [false; 256];
        let mut count0 = 0u32;
        let mut count1 = 0u32;

        for order in (1..=self.history.len().min(MAX_ORDER)).rev() {
            let Some(context) = self.context_for_order(order) else {
                continue;
            };
            let stats = context.prefix_stats(self.current_byte, self.used_bits, &excluded);
            if stats.total == 0 {
                continue;
            }

            count0 = count0.saturating_add(stats.count0);
            count1 = count1.saturating_add(stats.count1);
            context.exclude_all(&mut excluded);
        }

        let stats = self
            .order0
            .prefix_stats(self.current_byte, self.used_bits, &excluded);
        if stats.total > 0 {
            count0 = count0.saturating_add(stats.count0);
            count1 = count1.saturating_add(stats.count1);
            self.order0.exclude_all(&mut excluded);
        }

        let mut tail0 = 0u32;
        let mut tail1 = 0u32;
        for symbol in 0..=u8::MAX {
            if excluded[symbol as usize] || !byte_matches_prefix(symbol, self.current_byte, self.used_bits)
            {
                continue;
            }
            if next_bit(symbol, self.used_bits) == 0 {
                tail0 += 1;
            } else {
                tail1 += 1;
            }
        }

        count0 = count0.saturating_add(tail0);
        count1 = count1.saturating_add(tail1);

        let total = count0 + count1;
        if total == 0 {
            0.5
        } else {
            (count1 as f64 + 0.5) / (total as f64 + 1.0)
        }
    }

    fn observe_bit(&mut self, bit: u8) {
        self.current_byte = (self.current_byte << 1) | bit;
        self.used_bits += 1;

        if self.used_bits == 8 {
            let byte = self.current_byte;
            self.observe_byte(byte);
            self.history.push(byte);
            self.current_byte = 0;
            self.used_bits = 0;
        }
    }

    fn observe_byte(&mut self, symbol: u8) {
        self.order0.observe(symbol);

        for order in 1..=self.history.len().min(MAX_ORDER) {
            self.contexts[order - 1]
                .entry(self.history.key(order))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }

    fn context_for_order(&self, order: usize) -> Option<&Context> {
        self.contexts
            .get(order - 1)
            .and_then(|contexts| contexts.get(&self.history.key(order)))
    }
}

struct Context {
    counts: Vec<SymbolCount>,
    total: u32,
}

#[derive(Clone, Copy)]
struct SymbolCount {
    symbol: u8,
    count: u16,
}

#[derive(Clone, Copy)]
struct PrefixStats {
    total: u32,
    count0: u32,
    count1: u32,
}

impl Context {
    fn new() -> Self {
        Self {
            counts: Vec::new(),
            total: 0,
        }
    }

    fn observe(&mut self, symbol: u8) {
        match self.find(symbol) {
            Some(index) => {
                self.counts[index].count = self.counts[index].count.saturating_add(1);
            }
            None => {
                let index = self
                    .counts
                    .binary_search_by_key(&symbol, |entry| entry.symbol)
                    .unwrap_or_else(|index| index);
                self.counts.insert(index, SymbolCount { symbol, count: 1 });
            }
        }

        self.total = self.total.saturating_add(1);
        if self.total >= MAX_CONTEXT_TOTAL {
            self.rescale();
        }
    }

    fn prefix_stats(&self, prefix: u8, used_bits: u8, excluded: &[bool; 256]) -> PrefixStats {
        let mut count0 = 0u32;
        let mut count1 = 0u32;

        for entry in &self.counts {
            if excluded[entry.symbol as usize] || !byte_matches_prefix(entry.symbol, prefix, used_bits)
            {
                continue;
            }
            if next_bit(entry.symbol, used_bits) == 0 {
                count0 += u32::from(entry.count);
            } else {
                count1 += u32::from(entry.count);
            }
        }

        PrefixStats {
            total: count0 + count1,
            count0,
            count1,
        }
    }

    fn exclude_all(&self, excluded: &mut [bool; 256]) {
        for entry in &self.counts {
            excluded[entry.symbol as usize] = true;
        }
    }

    fn find(&self, symbol: u8) -> Option<usize> {
        self.counts
            .binary_search_by_key(&symbol, |entry| entry.symbol)
            .ok()
    }

    fn rescale(&mut self) {
        self.total = 0;
        for entry in &mut self.counts {
            entry.count = entry.count.div_ceil(2).max(1);
            self.total += u32::from(entry.count);
        }
    }
}

struct ByteHistory {
    bytes: VecDeque<u8>,
    max_order: usize,
}

impl ByteHistory {
    fn new(max_order: usize) -> Self {
        Self {
            bytes: VecDeque::with_capacity(max_order),
            max_order,
        }
    }

    fn len(&self) -> usize {
        self.bytes.len()
    }

    fn push(&mut self, byte: u8) {
        if self.bytes.len() == self.max_order {
            self.bytes.pop_front();
        }
        self.bytes.push_back(byte);
    }

    fn key(&self, order: usize) -> u64 {
        self.bytes
            .iter()
            .rev()
            .take(order)
            .enumerate()
            .fold(0u64, |key, (shift, byte)| {
                key | (u64::from(*byte) << (shift * 8))
            })
    }
}

fn byte_matches_prefix(symbol: u8, prefix: u8, used_bits: u8) -> bool {
    if used_bits == 0 {
        return true;
    }

    let mask = if used_bits == 8 {
        u8::MAX
    } else {
        u8::MAX << (8 - used_bits)
    };
    (symbol & mask) == (prefix << (8 - used_bits))
}

fn next_bit(symbol: u8, used_bits: u8) -> u8 {
    (symbol >> (7 - used_bits)) & 1
}

fn encode_probability(bit: u8, p1: f64, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
    let scale = 16384.0;
    let p1 = p1.clamp(1.0 / scale, 1.0 - (1.0 / scale));
    let w1 = (p1 * scale).round().max(1.0) as u32;
    let w0 = ((1.0 - p1) * scale).round().max(1.0) as u32;
    match bit {
        0 => encoder.encode(0, w0, w0 + w1),
        1 => encoder.encode(w0, w1, w0 + w1),
        _ => Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "bit out of range",
        )),
    }
}

fn decode_probability(p1: f64, decoder: &mut ArithmeticDecoder<'_>) -> io::Result<u8> {
    let scale = 16384.0;
    let p1 = p1.clamp(1.0 / scale, 1.0 - (1.0 / scale));
    let w1 = (p1 * scale).round().max(1.0) as u32;
    let w0 = ((1.0 - p1) * scale).round().max(1.0) as u32;
    let target = decoder.target(w0 + w1)?;
    if target < w0 {
        decoder.consume(0, w0, w0 + w1)?;
        Ok(0)
    } else {
        decoder.consume(w0, w1, w0 + w1)?;
        Ok(1)
    }
}

struct ArithmeticEncoder {
    low: u64,
    high: u64,
    pending: usize,
    bits: BitWriter,
}

impl ArithmeticEncoder {
    fn new() -> Self {
        Self {
            low: 0,
            high: MAX_RANGE,
            pending: 0,
            bits: BitWriter::default(),
        }
    }

    fn encode(&mut self, cum: u32, freq: u32, total: u32) -> io::Result<()> {
        if freq == 0 || total == 0 || cum > total || freq > total - cum {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid arithmetic coding frequencies",
            ));
        }

        let range = self.high - self.low + 1;
        self.high = self.low + (range * u64::from(cum + freq) / u64::from(total)) - 1;
        self.low += range * u64::from(cum) / u64::from(total);

        loop {
            if self.high < HALF {
                self.emit_bit(0)?;
            } else if self.low >= HALF {
                self.emit_bit(1)?;
                self.low -= HALF;
                self.high -= HALF;
            } else if self.low >= QUARTER && self.high < THREE_QUARTERS {
                self.pending += 1;
                self.low -= QUARTER;
                self.high -= QUARTER;
            } else {
                break;
            }

            self.low <<= 1;
            self.high = (self.high << 1) | 1;
        }

        Ok(())
    }

    fn finish(mut self) -> io::Result<Vec<u8>> {
        self.pending += 1;
        if self.low < QUARTER {
            self.emit_bit(0)?;
        } else {
            self.emit_bit(1)?;
        }
        Ok(self.bits.finish())
    }

    fn emit_bit(&mut self, bit: u8) -> io::Result<()> {
        self.bits.write_bit(bit)?;
        let fill = if bit == 0 { 1 } else { 0 };
        for _ in 0..self.pending {
            self.bits.write_bit(fill)?;
        }
        self.pending = 0;
        Ok(())
    }
}

struct ArithmeticDecoder<'a> {
    low: u64,
    high: u64,
    code: u64,
    bits: BitReader<'a>,
}

impl<'a> ArithmeticDecoder<'a> {
    fn new(payload: &'a [u8]) -> io::Result<Self> {
        let mut bits = BitReader::new(payload);
        let mut code = 0u64;
        for _ in 0..STATE_BITS {
            code = (code << 1) | u64::from(bits.read_bit_or_zero()?);
        }

        Ok(Self {
            low: 0,
            high: MAX_RANGE,
            code,
            bits,
        })
    }

    fn target(&mut self, total: u32) -> io::Result<u32> {
        if total == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid arithmetic coding total",
            ));
        }

        let range = self.high - self.low + 1;
        Ok((((self.code - self.low + 1) * u64::from(total) - 1) / range) as u32)
    }

    fn consume(&mut self, cum: u32, freq: u32, total: u32) -> io::Result<()> {
        if freq == 0 || total == 0 || cum > total || freq > total - cum {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid arithmetic coding frequencies",
            ));
        }

        let range = self.high - self.low + 1;
        self.high = self.low + (range * u64::from(cum + freq) / u64::from(total)) - 1;
        self.low += range * u64::from(cum) / u64::from(total);

        loop {
            if self.high < HALF {
            } else if self.low >= HALF {
                self.low -= HALF;
                self.high -= HALF;
                self.code -= HALF;
            } else if self.low >= QUARTER && self.high < THREE_QUARTERS {
                self.low -= QUARTER;
                self.high -= QUARTER;
                self.code -= QUARTER;
            } else {
                break;
            }

            self.low <<= 1;
            self.high = (self.high << 1) | 1;
            self.code = (self.code << 1) | u64::from(self.bits.read_bit_or_zero()?);
        }

        Ok(())
    }
}

struct ByteBits {
    byte: u8,
    shift: i8,
}

impl ByteBits {
    fn new(byte: u8) -> Self {
        Self { byte, shift: 7 }
    }
}

impl Iterator for ByteBits {
    type Item = u8;

    fn next(&mut self) -> Option<Self::Item> {
        if self.shift < 0 {
            return None;
        }

        let bit = (self.byte >> self.shift) & 1;
        self.shift -= 1;
        Some(bit)
    }
}

struct ByteCollector {
    bytes: Vec<u8>,
    current: u8,
    used_bits: u8,
}

impl ByteCollector {
    fn with_capacity(capacity: usize) -> Self {
        Self {
            bytes: Vec::with_capacity(capacity),
            current: 0,
            used_bits: 0,
        }
    }

    fn push(&mut self, bit: u8) -> io::Result<()> {
        if bit > 1 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "decoded bit out of range",
            ));
        }

        self.current = (self.current << 1) | bit;
        self.used_bits += 1;
        if self.used_bits == 8 {
            self.bytes.push(self.current);
            self.current = 0;
            self.used_bits = 0;
        }

        Ok(())
    }

    fn len(&self) -> usize {
        self.bytes.len()
    }

    fn finish(self) -> io::Result<Vec<u8>> {
        if self.used_bits != 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "decoded stream ended mid-byte",
            ));
        }

        Ok(self.bytes)
    }
}

#[derive(Default)]
struct BitWriter {
    bytes: Vec<u8>,
    current: u8,
    used_bits: u8,
}

impl BitWriter {
    fn write_bit(&mut self, bit: u8) -> io::Result<()> {
        if bit > 1 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "bit value out of range",
            ));
        }

        self.current = (self.current << 1) | bit;
        self.used_bits += 1;
        if self.used_bits == 8 {
            self.bytes.push(self.current);
            self.current = 0;
            self.used_bits = 0;
        }

        Ok(())
    }

    fn finish(mut self) -> Vec<u8> {
        if self.used_bits != 0 {
            self.current <<= 8 - self.used_bits;
            self.bytes.push(self.current);
        }
        self.bytes
    }
}

struct BitReader<'a> {
    bytes: &'a [u8],
    index: usize,
    used_bits: u8,
}

impl<'a> BitReader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self {
            bytes,
            index: 0,
            used_bits: 0,
        }
    }

    fn read_bit_or_zero(&mut self) -> io::Result<u8> {
        if self.index >= self.bytes.len() {
            return Ok(0);
        }

        let byte = self.bytes[self.index];
        let bit = (byte >> (7 - self.used_bits)) & 1;
        self.used_bits += 1;
        if self.used_bits == 8 {
            self.used_bits = 0;
            self.index += 1;
        }

        Ok(bit)
    }
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
    fn roundtrip_text() {
        roundtrip(b"banana bandana banana bandana banana bandana");
    }

    #[test]
    fn roundtrip_binary() {
        let input: Vec<u8> = (0..=255).cycle().take(4096).collect();
        roundtrip(&input);
    }

    #[test]
    fn roundtrip_empty() {
        roundtrip(b"");
    }

    fn roundtrip(input: &[u8]) {
        let mut compressed = Vec::new();
        compress(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
