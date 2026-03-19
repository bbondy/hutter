use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"PMIX";
const BIT_MAX_ORDER: usize = 64;
const BYTE_MAX_ORDER: usize = 6;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const MIX_LEARNING_RATE: f64 = 0.2;
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

    let mut model = HybridModel::new(BIT_MAX_ORDER, BYTE_MAX_ORDER);
    let mut encoder = ArithmeticEncoder::new();

    for &byte in &data {
        for bit in ByteBits::new(byte) {
            model.encode_bit(bit, &mut encoder)?;
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

    let mut model = HybridModel::new(BIT_MAX_ORDER, BYTE_MAX_ORDER);
    let mut decoder = ArithmeticDecoder::new(&payload)?;
    let mut restored = ByteCollector::with_capacity(original_size);

    while restored.len() < original_size {
        let bit = model.decode_bit(&mut decoder)?;
        restored.push(bit)?;
        model.observe_bit(bit);
    }

    output.write_all(restored.finish()?.as_slice())?;
    Ok(())
}

struct HybridModel {
    bit_order0: BitContext,
    bit_contexts: Vec<HashMap<u64, BitContext>>,
    byte_order0: ByteContext,
    byte_contexts: Vec<HashMap<u64, ByteContext>>,
    mixer: HybridMixer,
    bit_history: BitHistory,
    byte_history: ByteHistory,
    current_byte: u8,
    used_bits: u8,
    bit_max_order: usize,
    byte_max_order: usize,
}

impl HybridModel {
    fn new(bit_max_order: usize, byte_max_order: usize) -> Self {
        Self {
            bit_order0: BitContext::new(),
            bit_contexts: (0..bit_max_order).map(|_| HashMap::new()).collect(),
            byte_order0: ByteContext::new(),
            byte_contexts: (0..byte_max_order).map(|_| HashMap::new()).collect(),
            mixer: HybridMixer::new(bit_max_order, byte_max_order),
            bit_history: BitHistory::new(bit_max_order),
            byte_history: ByteHistory::new(byte_max_order),
            current_byte: 0,
            used_bits: 0,
            bit_max_order,
            byte_max_order,
        }
    }

    fn encode_bit(&self, bit: u8, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
        let p1 = self.mixed_probability();
        encode_probability(bit, p1, encoder)
    }

    fn decode_bit(&self, decoder: &mut ArithmeticDecoder<'_>) -> io::Result<u8> {
        let p1 = self.mixed_probability();
        decode_probability(p1, decoder)
    }

    fn observe_bit(&mut self, bit: u8) {
        let predictions = self.predictions();
        self.mixer.observe(bit, &predictions);

        self.bit_order0.observe(bit);
        for order in 1..=self.bit_history.len().min(self.bit_max_order) {
            self.bit_contexts[order - 1]
                .entry(self.bit_history.key(order))
                .or_insert_with(BitContext::new)
                .observe(bit);
        }
        self.bit_history.push(bit);

        self.current_byte = (self.current_byte << 1) | bit;
        self.used_bits += 1;
        if self.used_bits == 8 {
            let byte = self.current_byte;
            self.byte_order0.observe(byte);
            for order in 1..=self.byte_history.len().min(self.byte_max_order) {
                self.byte_contexts[order - 1]
                    .entry(self.byte_history.key(order))
                    .or_insert_with(ByteContext::new)
                    .observe(byte);
            }
            self.byte_history.push(byte);
            self.current_byte = 0;
            self.used_bits = 0;
        }
    }

    fn mixed_probability(&self) -> f64 {
        let predictions = self.predictions();
        self.mixer.mixed_probability(&predictions)
    }

    fn predictions(&self) -> Predictions {
        let mut bit_predictions = Vec::with_capacity(self.bit_max_order + 1);
        bit_predictions.push(OrderProbability {
            order: 0,
            p1: self.bit_order0.probability(),
        });
        for order in 1..=self.bit_history.len().min(self.bit_max_order) {
            let context = self.bit_contexts[order - 1].get(&self.bit_history.key(order));
            bit_predictions.push(OrderProbability {
                order,
                p1: context.and_then(BitContext::probability),
            });
        }

        let mut byte_predictions = Vec::with_capacity(self.byte_max_order + 1);
        byte_predictions.push(OrderProbability {
            order: 0,
            p1: self
                .byte_order0
                .bit_probability(self.current_byte, self.used_bits),
        });
        for order in 1..=self.byte_history.len().min(self.byte_max_order) {
            let context = self.byte_contexts[order - 1].get(&self.byte_history.key(order));
            byte_predictions.push(OrderProbability {
                order,
                p1: context.and_then(|ctx| ctx.bit_probability(self.current_byte, self.used_bits)),
            });
        }

        Predictions {
            bit: bit_predictions,
            byte: byte_predictions,
        }
    }
}

struct Predictions {
    bit: Vec<OrderProbability>,
    byte: Vec<OrderProbability>,
}

#[derive(Clone, Copy)]
struct OrderProbability {
    order: usize,
    p1: Option<f64>,
}

struct HybridMixer {
    bit_weights: Vec<[f64; 8]>,
    byte_weights: Vec<[f64; 8]>,
    bit_position: usize,
}

impl HybridMixer {
    fn new(bit_max_order: usize, byte_max_order: usize) -> Self {
        let bit_weights = (0..=bit_max_order)
            .map(|order| [bit_initial_weight(order); 8])
            .collect();
        let byte_weights = (0..=byte_max_order)
            .map(|order| [byte_initial_weight(order); 8])
            .collect();
        Self {
            bit_weights,
            byte_weights,
            bit_position: 0,
        }
    }

    fn mixed_probability(&self, predictions: &Predictions) -> f64 {
        let bp = self.bit_position;
        let mut logit_sum = 0.0;
        let mut any_context = false;

        for prediction in &predictions.bit {
            if let Some(p1) = prediction.p1 {
                logit_sum += self.bit_weights[prediction.order][bp] * stretch(p1);
                any_context = true;
            }
        }
        for prediction in &predictions.byte {
            if let Some(p1) = prediction.p1 {
                logit_sum += self.byte_weights[prediction.order][bp] * stretch(p1);
                any_context = true;
            }
        }

        if !any_context { 0.5 } else { squash(logit_sum) }
    }

    fn observe(&mut self, bit: u8, predictions: &Predictions) {
        let bp = self.bit_position;
        let mixed = self.mixed_probability(predictions);
        let error = f64::from(bit) - mixed;

        for prediction in &predictions.bit {
            if let Some(p1) = prediction.p1 {
                self.bit_weights[prediction.order][bp] += MIX_LEARNING_RATE * error * stretch(p1);
                self.bit_weights[prediction.order][bp] =
                    self.bit_weights[prediction.order][bp].clamp(-6.0, 6.0);
            }
        }
        for prediction in &predictions.byte {
            if let Some(p1) = prediction.p1 {
                self.byte_weights[prediction.order][bp] += MIX_LEARNING_RATE * error * stretch(p1);
                self.byte_weights[prediction.order][bp] =
                    self.byte_weights[prediction.order][bp].clamp(-6.0, 6.0);
            }
        }

        self.bit_position = (self.bit_position + 1) % 8;
    }
}

fn bit_initial_weight(order: usize) -> f64 {
    match order {
        0 => 0.2,
        1..=8 => 0.2 + (order as f64 * 0.11),
        9..=16 => 1.08 + ((order - 8) as f64 * 0.08),
        17..=32 => 1.72 + ((order - 16) as f64 * 0.045),
        _ => 2.44 + ((order - 32) as f64 * 0.02),
    }
}

fn byte_initial_weight(order: usize) -> f64 {
    match order {
        0 => 0.2,
        1 => 0.4,
        2 => 0.7,
        3 => 1.0,
        4 => 1.3,
        5 => 1.7,
        _ => 2.0,
    }
}

struct BitContext {
    counts: [u16; 2],
    total: u32,
}

impl BitContext {
    fn new() -> Self {
        Self {
            counts: [0, 0],
            total: 0,
        }
    }

    fn observe(&mut self, bit: u8) {
        self.counts[bit as usize] = self.counts[bit as usize].saturating_add(1);
        self.total = self.total.saturating_add(1);
        if self.total >= MAX_CONTEXT_TOTAL {
            self.rescale();
        }
    }

    fn probability(&self) -> Option<f64> {
        let total = u32::from(self.counts[0]) + u32::from(self.counts[1]);
        if total == 0 {
            None
        } else {
            Some((f64::from(self.counts[1]) + 0.5) / (f64::from(total) + 1.0))
        }
    }

    fn rescale(&mut self) {
        self.total = 0;
        for count in &mut self.counts {
            if *count > 0 {
                *count = count.div_ceil(2).max(1);
            }
            self.total += u32::from(*count);
        }
    }
}

struct ByteContext {
    counts: Vec<SymbolCount>,
    total: u32,
}

#[derive(Clone, Copy)]
struct SymbolCount {
    symbol: u8,
    count: u16,
}

impl ByteContext {
    fn new() -> Self {
        Self {
            counts: Vec::new(),
            total: 0,
        }
    }

    fn observe(&mut self, symbol: u8) {
        match self
            .counts
            .binary_search_by_key(&symbol, |entry| entry.symbol)
        {
            Ok(index) => {
                self.counts[index].count = self.counts[index].count.saturating_add(1);
            }
            Err(index) => self.counts.insert(index, SymbolCount { symbol, count: 1 }),
        }

        self.total = self.total.saturating_add(1);
        if self.total >= MAX_CONTEXT_TOTAL {
            self.rescale();
        }
    }

    fn bit_probability(&self, prefix: u8, used_bits: u8) -> Option<f64> {
        let mut count0 = 0u32;
        let mut count1 = 0u32;

        for entry in &self.counts {
            if byte_matches_prefix(entry.symbol, prefix, used_bits) {
                let bit = next_bit(entry.symbol, used_bits);
                if bit == 0 {
                    count0 += u32::from(entry.count);
                } else {
                    count1 += u32::from(entry.count);
                }
            }
        }

        let total = count0 + count1;
        if total == 0 {
            None
        } else {
            Some((count1 as f64 + 0.5) / (total as f64 + 1.0))
        }
    }

    fn rescale(&mut self) {
        self.total = 0;
        for entry in &mut self.counts {
            entry.count = entry.count.div_ceil(2).max(1);
            self.total += u32::from(entry.count);
        }
    }
}

#[derive(Clone, Copy)]
struct BitHistory {
    bits: u64,
    len: usize,
    max_order: usize,
}

impl BitHistory {
    fn new(max_order: usize) -> Self {
        Self {
            bits: 0,
            len: 0,
            max_order,
        }
    }

    fn len(&self) -> usize {
        self.len
    }

    fn push(&mut self, bit: u8) {
        let mask = history_mask(self.max_order);
        self.bits = ((self.bits << 1) | u64::from(bit)) & mask;
        self.len = (self.len + 1).min(self.max_order);
    }

    fn key(&self, order: usize) -> u64 {
        self.bits & history_mask(order)
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

fn history_mask(order: usize) -> u64 {
    if order >= u64::BITS as usize {
        u64::MAX
    } else {
        (1u64 << order) - 1
    }
}

fn stretch(p: f64) -> f64 {
    let p = p.clamp(0.001, 0.999);
    (p / (1.0 - p)).ln()
}

fn squash(logit: f64) -> f64 {
    1.0 / (1.0 + (-logit).exp())
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
        roundtrip(b"banana bandana banana bandana");
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
