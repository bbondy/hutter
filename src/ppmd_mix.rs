use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"PDMX";
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
            let predictions = model.predictions();
            model.encode_bit(bit, &predictions, &mut encoder)?;
            model.observe_bit(bit, &predictions);
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
        let predictions = model.predictions();
        let bit = model.decode_bit(&predictions, &mut decoder)?;
        restored.push(bit)?;
        model.observe_bit(bit, &predictions);
    }

    output.write_all(restored.finish()?.as_slice())?;
    Ok(())
}

struct HybridModel {
    bit_order0: BitContext,
    bit_contexts: Vec<HashMap<u64, BitContext>>,
    ppmd: PpmdByteModel,
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
            ppmd: PpmdByteModel::new(byte_max_order),
            mixer: HybridMixer::new(bit_max_order),
            bit_history: BitHistory::new(bit_max_order),
            byte_history: ByteHistory::new(byte_max_order),
            current_byte: 0,
            used_bits: 0,
            bit_max_order,
            byte_max_order,
        }
    }

    fn encode_bit(
        &self,
        bit: u8,
        predictions: &Predictions,
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        encode_probability(bit, self.mixer.mixed_probability(predictions), encoder)
    }

    fn decode_bit(
        &self,
        predictions: &Predictions,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        decode_probability(self.mixer.mixed_probability(predictions), decoder)
    }

    fn observe_bit(&mut self, bit: u8, predictions: &Predictions) {
        self.mixer.observe(bit, predictions);

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
            self.ppmd.observe(byte, &self.byte_history);
            self.byte_history.push(byte);
            self.current_byte = 0;
            self.used_bits = 0;
        }
    }

    fn predictions(&mut self) -> Predictions {
        let mut bit_predictions = Vec::with_capacity(self.bit_max_order + 1);
        bit_predictions.push(OrderProbability {
            order: 0,
            p1: self.bit_order0.probability(),
        });
        for order in 1..=self.bit_history.len().min(self.bit_max_order) {
            bit_predictions.push(OrderProbability {
                order,
                p1: self.bit_contexts[order - 1]
                    .get(&self.bit_history.key(order))
                    .and_then(BitContext::probability),
            });
        }

        Predictions {
            bit: bit_predictions,
            ppmd_p1: self
                .ppmd
                .bit_probability(self.current_byte, self.used_bits, &self.byte_history),
        }
    }
}

struct Predictions {
    bit: Vec<OrderProbability>,
    ppmd_p1: Option<f64>,
}

#[derive(Clone, Copy)]
struct OrderProbability {
    order: usize,
    p1: Option<f64>,
}

struct HybridMixer {
    bit_weights: Vec<[f64; 8]>,
    ppmd_weight: [f64; 8],
    bit_position: usize,
}

impl HybridMixer {
    fn new(bit_max_order: usize) -> Self {
        let bit_weights = (0..=bit_max_order)
            .map(|order| [bit_initial_weight(order); 8])
            .collect();
        Self {
            bit_weights,
            ppmd_weight: [2.4; 8],
            bit_position: 0,
        }
    }

    fn mixed_probability(&self, predictions: &Predictions) -> f64 {
        let bp = self.bit_position;
        let mut logit_sum = 0.0;
        let mut any = false;

        for prediction in &predictions.bit {
            if let Some(p1) = prediction.p1 {
                logit_sum += self.bit_weights[prediction.order][bp] * stretch(p1);
                any = true;
            }
        }
        if let Some(p1) = predictions.ppmd_p1 {
            logit_sum += self.ppmd_weight[bp] * stretch(p1);
            any = true;
        }

        if any { squash(logit_sum) } else { 0.5 }
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
        if let Some(p1) = predictions.ppmd_p1 {
            self.ppmd_weight[bp] += MIX_LEARNING_RATE * error * stretch(p1);
            self.ppmd_weight[bp] = self.ppmd_weight[bp].clamp(-6.0, 6.0);
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

struct PpmdByteModel {
    order0: ByteContext,
    contexts: Vec<HashMap<u64, ByteContext>>,
    distribution: [f64; 256],
    distribution_ready: bool,
}

impl PpmdByteModel {
    fn new(max_order: usize) -> Self {
        Self {
            order0: ByteContext::new(),
            contexts: (0..max_order).map(|_| HashMap::new()).collect(),
            distribution: [0.0; 256],
            distribution_ready: false,
        }
    }

    fn observe(&mut self, symbol: u8, history: &ByteHistory) {
        self.order0.observe(symbol);
        for order in 1..=history.len().min(self.contexts.len()) {
            self.contexts[order - 1]
                .entry(history.key(order))
                .or_insert_with(ByteContext::new)
                .observe(symbol);
        }
        self.distribution_ready = false;
    }

    fn bit_probability(
        &mut self,
        prefix: u8,
        used_bits: u8,
        history: &ByteHistory,
    ) -> Option<f64> {
        self.ensure_distribution(history);

        let mut count0 = 0.0;
        let mut count1 = 0.0;
        for symbol in 0..=u8::MAX {
            let weight = self.distribution[symbol as usize];
            if weight == 0.0 || !byte_matches_prefix(symbol, prefix, used_bits) {
                continue;
            }
            if next_bit(symbol, used_bits) == 0 {
                count0 += weight;
            } else {
                count1 += weight;
            }
        }

        let total = count0 + count1;
        if total == 0.0 {
            None
        } else {
            Some((count1 + 1e-9) / (total + 2e-9))
        }
    }

    fn ensure_distribution(&mut self, history: &ByteHistory) {
        if self.distribution_ready {
            return;
        }

        self.distribution.fill(0.0);
        let mut excluded = [false; 256];
        let mut remaining_mass = 1.0;

        for order in (1..=history.len().min(self.contexts.len())).rev() {
            let Some((stats, counts)) = self.contexts[order - 1].get(&history.key(order)).map(|ctx| {
                (ctx.stats(&excluded), ctx.counts.iter().copied().collect::<Vec<_>>())
            }) else {
                continue;
            };
            if stats.total == 0 || remaining_mass <= 0.0 {
                continue;
            }

            let total = f64::from(stats.total_with_escape());
            for entry in counts {
                if excluded[entry.symbol as usize] {
                    continue;
                }
                self.distribution[entry.symbol as usize] += remaining_mass * (f64::from(entry.count) / total);
                excluded[entry.symbol as usize] = true;
            }
            remaining_mass *= f64::from(stats.escape_freq) / total;
        }

        let stats = self.order0.stats(&excluded);
        if stats.total > 0 && remaining_mass > 0.0 {
            let total = f64::from(stats.total_with_escape());
            let counts: Vec<_> = self.order0.counts.iter().copied().collect();
            for entry in counts {
                if excluded[entry.symbol as usize] {
                    continue;
                }
                self.distribution[entry.symbol as usize] += remaining_mass * (f64::from(entry.count) / total);
                excluded[entry.symbol as usize] = true;
            }
            remaining_mass *= f64::from(stats.escape_freq) / total;
        }

        let unseen = excluded.iter().filter(|&&x| !x).count();
        if unseen > 0 && remaining_mass > 0.0 {
            let share = remaining_mass / unseen as f64;
            for symbol in 0..=u8::MAX {
                if !excluded[symbol as usize] {
                    self.distribution[symbol as usize] += share;
                }
            }
        }

        self.distribution_ready = true;
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
        match self.counts.binary_search_by_key(&symbol, |entry| entry.symbol) {
            Ok(index) => self.counts[index].count = self.counts[index].count.saturating_add(1),
            Err(index) => self.counts.insert(index, SymbolCount { symbol, count: 1 }),
        }

        self.total = self.total.saturating_add(1);
        if self.total >= MAX_CONTEXT_TOTAL {
            self.rescale();
        }
    }

    fn rescale(&mut self) {
        self.total = 0;
        for entry in &mut self.counts {
            entry.count = entry.count.div_ceil(2).max(1);
            self.total += u32::from(entry.count);
        }
    }

    fn stats(&self, excluded: &[bool; 256]) -> FilteredStats {
        let mut total = 0u32;
        let mut symbols = 0usize;
        for entry in &self.counts {
            if excluded[entry.symbol as usize] {
                continue;
            }
            total += u32::from(entry.count);
            symbols += 1;
        }

        let escape_freq = match symbols {
            0 => 0,
            1 => 1,
            _ => (symbols as u32).div_ceil(2),
        };
        FilteredStats { total, escape_freq }
    }
}

#[derive(Clone, Copy)]
struct FilteredStats {
    total: u32,
    escape_freq: u32,
}

impl FilteredStats {
    fn total_with_escape(self) -> u32 {
        self.total + self.escape_freq
    }
}

struct BitContext {
    counts: [u16; 2],
    total: u32,
}

impl BitContext {
    fn new() -> Self {
        Self { counts: [0, 0], total: 0 }
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

#[derive(Clone, Copy)]
struct BitHistory {
    bits: u64,
    len: usize,
    max_order: usize,
}

impl BitHistory {
    fn new(max_order: usize) -> Self {
        Self { bits: 0, len: 0, max_order }
    }
    fn len(&self) -> usize { self.len }
    fn push(&mut self, bit: u8) {
        let mask = history_mask(self.max_order);
        self.bits = ((self.bits << 1) | u64::from(bit)) & mask;
        self.len = (self.len + 1).min(self.max_order);
    }
    fn key(&self, order: usize) -> u64 { self.bits & history_mask(order) }
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
    fn len(&self) -> usize { self.bytes.len() }
    fn push(&mut self, byte: u8) {
        if self.bytes.len() == self.max_order {
            self.bytes.pop_front();
        }
        self.bytes.push_back(byte);
    }
    fn key(&self, order: usize) -> u64 {
        self.bytes.iter().rev().take(order).enumerate().fold(0u64, |key, (shift, byte)| {
            key | (u64::from(*byte) << (shift * 8))
        })
    }
}

fn byte_matches_prefix(symbol: u8, prefix: u8, used_bits: u8) -> bool {
    if used_bits == 0 {
        return true;
    }
    let mask = if used_bits == 8 { u8::MAX } else { u8::MAX << (8 - used_bits) };
    (symbol & mask) == (prefix << (8 - used_bits))
}

fn next_bit(symbol: u8, used_bits: u8) -> u8 {
    (symbol >> (7 - used_bits)) & 1
}

fn history_mask(order: usize) -> u64 {
    if order >= u64::BITS as usize { u64::MAX } else { (1u64 << order) - 1 }
}

fn stretch(p: f64) -> f64 {
    let p = p.clamp(0.001, 0.999);
    (p / (1.0 - p)).ln()
}

fn squash(logit: f64) -> f64 { 1.0 / (1.0 + (-logit).exp()) }

fn encode_probability(bit: u8, p1: f64, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
    let scale = 16384.0;
    let p1 = p1.clamp(1.0 / scale, 1.0 - (1.0 / scale));
    let w1 = (p1 * scale).round().max(1.0) as u32;
    let w0 = ((1.0 - p1) * scale).round().max(1.0) as u32;
    match bit {
        0 => encoder.encode(0, w0, w0 + w1),
        1 => encoder.encode(w0, w1, w0 + w1),
        _ => Err(io::Error::new(io::ErrorKind::InvalidInput, "bit out of range")),
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
        Self { low: 0, high: MAX_RANGE, pending: 0, bits: BitWriter::default() }
    }
    fn encode(&mut self, cum: u32, freq: u32, total: u32) -> io::Result<()> {
        if freq == 0 || total == 0 || cum > total || freq > total - cum {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid arithmetic coding frequencies"));
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
        if self.low < QUARTER { self.emit_bit(0)?; } else { self.emit_bit(1)?; }
        Ok(self.bits.finish())
    }
    fn emit_bit(&mut self, bit: u8) -> io::Result<()> {
        self.bits.write_bit(bit)?;
        let fill = if bit == 0 { 1 } else { 0 };
        for _ in 0..self.pending { self.bits.write_bit(fill)?; }
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
        for _ in 0..STATE_BITS { code = (code << 1) | u64::from(bits.read_bit_or_zero()?); }
        Ok(Self { low: 0, high: MAX_RANGE, code, bits })
    }
    fn target(&mut self, total: u32) -> io::Result<u32> {
        if total == 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid arithmetic coding total"));
        }
        let range = self.high - self.low + 1;
        Ok((((self.code - self.low + 1) * u64::from(total) - 1) / range) as u32)
    }
    fn consume(&mut self, cum: u32, freq: u32, total: u32) -> io::Result<()> {
        if freq == 0 || total == 0 || cum > total || freq > total - cum {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid arithmetic coding frequencies"));
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

struct ByteBits { byte: u8, shift: i8 }
impl ByteBits { fn new(byte: u8) -> Self { Self { byte, shift: 7 } } }
impl Iterator for ByteBits {
    type Item = u8;
    fn next(&mut self) -> Option<Self::Item> {
        if self.shift < 0 { return None; }
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
        Self { bytes: Vec::with_capacity(capacity), current: 0, used_bits: 0 }
    }
    fn push(&mut self, bit: u8) -> io::Result<()> {
        if bit > 1 { return Err(io::Error::new(io::ErrorKind::InvalidData, "decoded bit out of range")); }
        self.current = (self.current << 1) | bit;
        self.used_bits += 1;
        if self.used_bits == 8 {
            self.bytes.push(self.current);
            self.current = 0;
            self.used_bits = 0;
        }
        Ok(())
    }
    fn len(&self) -> usize { self.bytes.len() }
    fn finish(self) -> io::Result<Vec<u8>> {
        if self.used_bits != 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "decoded stream ended mid-byte"));
        }
        Ok(self.bytes)
    }
}

#[derive(Default)]
struct BitWriter { bytes: Vec<u8>, current: u8, used_bits: u8 }
impl BitWriter {
    fn write_bit(&mut self, bit: u8) -> io::Result<()> {
        if bit > 1 { return Err(io::Error::new(io::ErrorKind::InvalidInput, "bit value out of range")); }
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

struct BitReader<'a> { bytes: &'a [u8], index: usize, used_bits: u8 }
impl<'a> BitReader<'a> {
    fn new(bytes: &'a [u8]) -> Self { Self { bytes, index: 0, used_bits: 0 } }
    fn read_bit_or_zero(&mut self) -> io::Result<u8> {
        if self.index >= self.bytes.len() { return Ok(0); }
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

    fn roundtrip(input: &[u8]) {
        let mut compressed = Vec::new();
        compress(input, &mut compressed).unwrap();
        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
