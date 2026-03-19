use std::collections::HashMap;
use std::io::{self, Read, Write};

const MAGIC_ORDER8: &[u8; 4] = b"PB08";
const MAGIC_ORDER16: &[u8; 4] = b"PB16";
const MAGIC_ORDER32: &[u8; 4] = b"PB32";
const MAGIC_ORDER64: &[u8; 4] = b"PB64";
const MAGIC_MIX: &[u8; 4] = b"PBMX";
const MAX_ORDER: usize = 64;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const MIX_LEARNING_RATE: f64 = 0.3;
const MIX_ESCAPE_FREQ: u32 = 8;
const STATE_BITS: u32 = 32;
const MAX_RANGE: u64 = (1u64 << STATE_BITS) - 1;
const HALF: u64 = 1u64 << (STATE_BITS - 1);
const QUARTER: u64 = HALF >> 1;
const THREE_QUARTERS: u64 = HALF + QUARTER;

pub fn magic_order8() -> &'static [u8; 4] {
    MAGIC_ORDER8
}

pub fn magic_order16() -> &'static [u8; 4] {
    MAGIC_ORDER16
}

pub fn magic_order32() -> &'static [u8; 4] {
    MAGIC_ORDER32
}

pub fn magic_order64() -> &'static [u8; 4] {
    MAGIC_ORDER64
}

pub fn magic_mix() -> &'static [u8; 4] {
    MAGIC_MIX
}

pub fn compress_order8<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER8, 8)
}

pub fn compress_order16<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER16, 16)
}

pub fn compress_order32<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER32, 32)
}

pub fn compress_order64<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER64, 64)
}

pub fn compress_mix<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_mixer(input, output, MAGIC_MIX, MAX_ORDER)
}

fn compress_with_order<R: Read, W: Write>(
    mut input: R,
    mut output: W,
    magic: &[u8; 4],
    max_order: usize,
) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(magic)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut model = Model::new();
    let mut encoder = ArithmeticEncoder::new();
    let mut history = BitHistory::new(max_order);

    for &byte in &data {
        for bit in ByteBits::new(byte) {
            model.encode_symbol(bit, &history, max_order, &mut encoder)?;
            model.observe(bit, &history, max_order);
            history.push(bit);
        }
    }

    output.write_all(&encoder.finish()?)?;
    Ok(())
}

fn compress_with_mixer<R: Read, W: Write>(
    mut input: R,
    mut output: W,
    magic: &[u8; 4],
    max_order: usize,
) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(magic)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut model = MixedModel::new(max_order);
    let mut encoder = ArithmeticEncoder::new();
    let mut history = BitHistory::new(max_order);

    for &byte in &data {
        for bit in ByteBits::new(byte) {
            model.encode_symbol(bit, &history, &mut encoder)?;
            model.observe(bit, &history);
            history.push(bit);
        }
    }

    output.write_all(&encoder.finish()?)?;
    Ok(())
}

pub fn decompress_order8<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER8, 8)
}

pub fn decompress_order16<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER16, 16)
}

pub fn decompress_order32<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER32, 32)
}

pub fn decompress_order64<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER64, 64)
}

pub fn decompress_mix<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_mixer(input, output, MAGIC_MIX, MAX_ORDER)
}

fn decompress_with_order<R: Read, W: Write>(
    mut input: R,
    mut output: W,
    expected_magic: &[u8; 4],
    max_order: usize,
) -> io::Result<()> {
    let mut magic = [0u8; 4];
    input.read_exact(&mut magic)?;
    if &magic != expected_magic {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid archive magic",
        ));
    }

    let original_size = read_u64(&mut input)? as usize;
    let mut payload = Vec::new();
    input.read_to_end(&mut payload)?;

    let mut model = Model::new();
    let mut decoder = ArithmeticDecoder::new(&payload)?;
    let mut history = BitHistory::new(max_order);
    let mut restored = ByteCollector::with_capacity(original_size);

    while restored.len() < original_size {
        let bit = model.decode_symbol(&history, max_order, &mut decoder)?;
        restored.push(bit)?;
        model.observe(bit, &history, max_order);
        history.push(bit);
    }

    output.write_all(restored.finish()?.as_slice())?;
    Ok(())
}

fn decompress_with_mixer<R: Read, W: Write>(
    mut input: R,
    mut output: W,
    expected_magic: &[u8; 4],
    max_order: usize,
) -> io::Result<()> {
    let mut magic = [0u8; 4];
    input.read_exact(&mut magic)?;
    if &magic != expected_magic {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid archive magic",
        ));
    }

    let original_size = read_u64(&mut input)? as usize;
    let mut payload = Vec::new();
    input.read_to_end(&mut payload)?;

    let mut model = MixedModel::new(max_order);
    let mut decoder = ArithmeticDecoder::new(&payload)?;
    let mut history = BitHistory::new(max_order);
    let mut restored = ByteCollector::with_capacity(original_size);

    while restored.len() < original_size {
        let bit = model.decode_symbol(&history, &mut decoder)?;
        restored.push(bit)?;
        model.observe(bit, &history);
        history.push(bit);
    }

    output.write_all(restored.finish()?.as_slice())?;
    Ok(())
}

struct Model {
    order0: Context,
    contexts: Vec<HashMap<u128, Context>>,
}

impl Model {
    fn new() -> Self {
        Self {
            order0: Context::new(),
            contexts: (0..MAX_ORDER).map(|_| HashMap::new()).collect(),
        }
    }

    fn encode_symbol(
        &self,
        symbol: u8,
        history: &BitHistory,
        max_order: usize,
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        for order in (1..=history.len().min(max_order)).rev() {
            if let Some(context) = self.context_for_order(order, history) {
                if !context_is_usable(order, context) {
                    continue;
                }
                if context.contains(symbol) {
                    return context.encode_symbol(symbol, encoder);
                }
                context.encode_escape(encoder)?;
            }
        }

        if self.order0.contains(symbol) {
            self.order0.encode_symbol(symbol, encoder)?;
        } else {
            self.order0.encode_escape(encoder)?;
            encoder.encode(u32::from(symbol), 1, 2)?;
        }

        Ok(())
    }

    fn decode_symbol(
        &self,
        history: &BitHistory,
        max_order: usize,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        for order in (1..=history.len().min(max_order)).rev() {
            if let Some(context) = self.context_for_order(order, history) {
                if !context_is_usable(order, context) {
                    continue;
                }
                if let Some(symbol) = context.decode_symbol(decoder)? {
                    return Ok(symbol);
                }
            }
        }

        if let Some(symbol) = self.order0.decode_symbol(decoder)? {
            return Ok(symbol);
        }

        let value = decoder.target(2)?;
        decoder.consume(value, 1, 2)?;
        Ok(value as u8)
    }

    fn observe(&mut self, symbol: u8, history: &BitHistory, max_order: usize) {
        self.order0.observe(symbol);

        for order in 1..=history.len().min(max_order) {
            self.contexts[order - 1]
                .entry(history.key(order))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }

    fn context_for_order(&self, order: usize, history: &BitHistory) -> Option<&Context> {
        self.contexts
            .get(order - 1)
            .and_then(|contexts| contexts.get(&history.key(order)))
    }
}

struct MixedModel {
    order0: Context,
    contexts: Vec<HashMap<u128, Context>>,
    mixer: OrderMixer,
    max_order: usize,
}

impl MixedModel {
    fn new(max_order: usize) -> Self {
        Self {
            order0: Context::new(),
            contexts: (0..max_order).map(|_| HashMap::new()).collect(),
            mixer: OrderMixer::new(max_order),
            max_order,
        }
    }

    fn encode_symbol(
        &self,
        symbol: u8,
        history: &BitHistory,
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        let candidates = self.mixed_candidates(history);
        encode_mixed_symbol(symbol, &candidates, encoder)
    }

    fn decode_symbol(
        &self,
        history: &BitHistory,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        let candidates = self.mixed_candidates(history);
        decode_mixed_symbol(&candidates, decoder)
    }

    fn observe(&mut self, symbol: u8, history: &BitHistory) {
        self.mixer.observe(symbol, &self.predictions(history));
        self.order0.observe(symbol);

        for order in 1..=history.len().min(self.max_order) {
            self.contexts[order - 1]
                .entry(history.key(order))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }

    fn mixed_candidates(&self, history: &BitHistory) -> Vec<WeightedSymbol> {
        self.mixer.combine(&self.predictions(history))
    }

    fn predictions(&self, history: &BitHistory) -> Vec<OrderPrediction> {
        let mut predictions = Vec::with_capacity(self.max_order + 1);
        predictions.push(OrderPrediction {
            order: 0,
            symbols: self.order0.top_symbols(2),
        });

        for order in 1..=history.len().min(self.max_order) {
            let context = self.contexts[order - 1].get(&history.key(order));
            predictions.push(OrderPrediction {
                order,
                symbols: context
                    .filter(|context| context_is_usable(order, context))
                    .map(|context| context.top_symbols(2))
                    .unwrap_or_default(),
            });
        }

        predictions
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct WeightedSymbol {
    symbol: u8,
    weight: u32,
}

#[derive(Clone, Debug)]
struct OrderPrediction {
    order: usize,
    symbols: Vec<(u8, u32)>,
}

struct OrderMixer {
    weights: Vec<[f64; 8]>, // per bit-position weights
    bit_position: usize,
}

impl OrderMixer {
    fn new(max_order: usize) -> Self {
        let weights = (0..=max_order)
            .map(|order| [initial_mix_weight(order); 8])
            .collect();
        Self {
            weights,
            bit_position: 0,
        }
    }

    fn combine(&self, predictions: &[OrderPrediction]) -> Vec<WeightedSymbol> {
        let mixed_p1 = self.mixed_probability(predictions);

        let scale = 16384.0;
        let w0 = ((1.0 - mixed_p1) * scale).round().max(1.0) as u32;
        let w1 = (mixed_p1 * scale).round().max(1.0) as u32;

        let mut candidates = Vec::with_capacity(2);
        candidates.push(WeightedSymbol {
            symbol: 0,
            weight: w0,
        });
        candidates.push(WeightedSymbol {
            symbol: 1,
            weight: w1,
        });
        candidates
    }

    fn observe(&mut self, symbol: u8, predictions: &[OrderPrediction]) {
        let bp = self.bit_position;
        let mixed_p1 = self.mixed_probability(predictions);
        let error = f64::from(symbol) - mixed_p1;

        for prediction in predictions {
            if let Some(p1) = Self::order_probability(prediction) {
                let stretched = Self::stretch(p1);
                self.weights[prediction.order][bp] += MIX_LEARNING_RATE * error * stretched;
            }
        }

        self.bit_position = (self.bit_position + 1) % 8;
    }

    fn mixed_probability(&self, predictions: &[OrderPrediction]) -> f64 {
        let bp = self.bit_position;
        let mut logit_sum = 0.0;
        let mut any_context = false;

        for prediction in predictions {
            if let Some(p1) = Self::order_probability(prediction) {
                logit_sum += self.weights[prediction.order][bp] * Self::stretch(p1);
                any_context = true;
            }
        }

        if !any_context {
            return 0.5;
        }

        Self::squash(logit_sum)
    }

    fn order_probability(prediction: &OrderPrediction) -> Option<f64> {
        if prediction.symbols.is_empty() {
            return None;
        }

        let mut count0 = 0u32;
        let mut count1 = 0u32;
        for &(symbol, count) in &prediction.symbols {
            match symbol {
                0 => count0 = count,
                _ => count1 = count,
            }
        }

        let total = count0 + count1;
        if total == 0 {
            return None;
        }

        // Laplace smoothing
        Some((count1 as f64 + 0.5) / (total as f64 + 1.0))
    }

    fn stretch(p: f64) -> f64 {
        let p = p.clamp(0.001, 0.999);
        (p / (1.0 - p)).ln()
    }

    fn squash(logit: f64) -> f64 {
        1.0 / (1.0 + (-logit).exp())
    }
}

fn initial_mix_weight(order: usize) -> f64 {
    match order {
        0 => 0.3,
        1..=8 => 0.3 + (order as f64 * 0.12),
        9..=16 => 1.3 + ((order - 8) as f64 * 0.09),
        17..=32 => 2.1 + ((order - 16) as f64 * 0.05),
        _ => 2.9 + ((order - 32) as f64 * 0.025),
    }
}

struct Context {
    counts: [u16; 2],
    total: u32,
}

impl Context {
    fn new() -> Self {
        Self {
            counts: [0, 0],
            total: 0,
        }
    }

    fn contains(&self, symbol: u8) -> bool {
        self.counts[symbol as usize] > 0
    }

    fn encode_symbol(&self, symbol: u8, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
        let cum = self.cumulative(symbol);
        let freq = u32::from(self.counts[symbol as usize]);
        encoder.encode(cum, freq, self.total_with_escape())
    }

    fn encode_escape(&self, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
        encoder.encode(self.total, self.escape_freq(), self.total_with_escape())
    }

    fn decode_symbol(&self, decoder: &mut ArithmeticDecoder<'_>) -> io::Result<Option<u8>> {
        let total = self.total_with_escape();
        let value = decoder.target(total)?;

        if value >= self.total {
            decoder.consume(self.total, self.escape_freq(), total)?;
            return Ok(None);
        }

        let zero_freq = u32::from(self.counts[0]);
        if value < zero_freq {
            decoder.consume(0, zero_freq, total)?;
            return Ok(Some(0));
        }

        let one_freq = u32::from(self.counts[1]);
        decoder.consume(zero_freq, one_freq, total)?;
        Ok(Some(1))
    }

    fn observe(&mut self, symbol: u8) {
        let slot = &mut self.counts[symbol as usize];
        *slot = slot.saturating_add(1);
        self.total = self.total.saturating_add(1);

        if self.total >= MAX_CONTEXT_TOTAL {
            self.rescale();
        }
    }

    fn cumulative(&self, symbol: u8) -> u32 {
        match symbol {
            0 => 0,
            _ => u32::from(self.counts[0]),
        }
    }

    fn escape_freq(&self) -> u32 {
        self.counts
            .iter()
            .filter(|&&count| count > 0)
            .count()
            .max(1) as u32
    }

    fn total_with_escape(&self) -> u32 {
        self.total + self.escape_freq()
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

    fn top_symbols(&self, limit: usize) -> Vec<(u8, u32)> {
        let mut top = Vec::new();

        for symbol in 0..=1u8 {
            let count = u32::from(self.counts[symbol as usize]);
            if count > 0 {
                top.push((symbol, count));
            }
        }

        top.sort_by(|left, right| right.1.cmp(&left.1).then_with(|| left.0.cmp(&right.0)));
        top.truncate(limit);
        top
    }
}

fn context_is_usable(order: usize, context: &Context) -> bool {
    context.total >= min_context_total(order)
}

fn min_context_total(order: usize) -> u32 {
    match order {
        0..=31 => 1,
        32..=63 => 3,
        _ => 5,
    }
}

fn encode_mixed_symbol(
    symbol: u8,
    candidates: &[WeightedSymbol],
    encoder: &mut ArithmeticEncoder,
) -> io::Result<()> {
    let total = mixed_total(candidates);
    let mut cum = 0u32;

    for candidate in candidates {
        if candidate.symbol == symbol {
            return encoder.encode(cum, candidate.weight, total);
        }
        cum = cum.saturating_add(candidate.weight);
    }

    encoder.encode(cum, MIX_ESCAPE_FREQ, total)?;
    encoder.encode(u32::from(symbol), 1, 2)
}

fn decode_mixed_symbol(
    candidates: &[WeightedSymbol],
    decoder: &mut ArithmeticDecoder<'_>,
) -> io::Result<u8> {
    let total = mixed_total(candidates);
    let target = decoder.target(total)?;
    let mut cum = 0u32;

    for candidate in candidates {
        if target < cum + candidate.weight {
            decoder.consume(cum, candidate.weight, total)?;
            return Ok(candidate.symbol);
        }
        cum = cum.saturating_add(candidate.weight);
    }

    decoder.consume(cum, MIX_ESCAPE_FREQ, total)?;
    let value = decoder.target(2)?;
    decoder.consume(value, 1, 2)?;
    Ok(value as u8)
}

fn mixed_total(candidates: &[WeightedSymbol]) -> u32 {
    candidates.iter().fold(MIX_ESCAPE_FREQ, |total, candidate| {
        total.saturating_add(candidate.weight)
    })
}

#[derive(Clone, Copy)]
struct BitHistory {
    bits: u64,
    len: usize,
    max_order: usize,
    current_byte: u8,
    used_bits: u8,
}

impl BitHistory {
    fn new(max_order: usize) -> Self {
        Self {
            bits: 0,
            len: 0,
            max_order,
            current_byte: 0,
            used_bits: 0,
        }
    }

    fn len(&self) -> usize {
        self.len
    }

    fn push(&mut self, bit: u8) {
        let mask = history_mask(self.max_order);
        self.bits = ((self.bits << 1) | u64::from(bit)) & mask;
        self.len = (self.len + 1).min(self.max_order);
        self.current_byte = (self.current_byte << 1) | bit;
        self.used_bits = (self.used_bits + 1) % 8;
        if self.used_bits == 0 {
            self.current_byte = 0;
        }
    }

    fn key(&self, order: usize) -> u128 {
        let suffix = u128::from(self.bits & history_mask(order));
        let bit_position = u128::from(self.used_bits);
        let prefix = u128::from(self.current_byte);

        suffix | (bit_position << order) | (prefix << (order + 3))
    }
}

fn history_mask(order: usize) -> u64 {
    if order >= u64::BITS as usize {
        u64::MAX
    } else {
        (1u64 << order) - 1
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
    use super::{
        OrderMixer, OrderPrediction, compress_mix, compress_order8, compress_order16,
        compress_order32, compress_order64, decompress_mix, decompress_order8, decompress_order16,
        decompress_order32, decompress_order64,
    };

    #[test]
    fn roundtrip_repeated_text_all_orders() {
        let input = b"banana bandana banana bandana banana bandana";
        roundtrip_mix(input);
        roundtrip_order8(input);
        roundtrip_order16(input);
        roundtrip_order32(input);
        roundtrip_order64(input);
    }

    #[test]
    fn roundtrip_binary_all_orders() {
        let input: Vec<u8> = (0..=255).cycle().take(4096).collect();
        roundtrip_mix(&input);
        roundtrip_order8(&input);
        roundtrip_order16(&input);
        roundtrip_order32(&input);
        roundtrip_order64(&input);
    }

    #[test]
    fn roundtrip_empty_input() {
        roundtrip_order8(b"");
        roundtrip_mix(b"");
    }

    #[test]
    fn order64_produces_distinct_archive_from_order32() {
        let mut input = Vec::new();
        for _ in 0..1024 {
            input.extend_from_slice(&[0x55, 0x54, 0x55, 0x57]);
        }

        let mut compressed32 = Vec::new();
        compress_order32(&input[..], &mut compressed32).unwrap();

        let mut compressed64 = Vec::new();
        compress_order64(&input[..], &mut compressed64).unwrap();

        assert_ne!(compressed64, compressed32);
    }

    #[test]
    fn gradient_mixer_adjusts_weights_toward_correct_prediction() {
        let mut mixer = OrderMixer::new(3);

        // Order 0 predicts bit=1 strongly
        let predictions = vec![OrderPrediction {
            order: 0,
            symbols: vec![(1, 10), (0, 1)],
        }];

        let bp = mixer.bit_position;
        let before = mixer.weights[0][bp];
        // Actual symbol is 1, matching the prediction — weight should increase
        mixer.observe(1, &predictions);
        let after = mixer.weights[0][bp];

        assert!(
            after > before,
            "weight should increase when prediction is correct: before={before}, after={after}"
        );

        // Now actual symbol is 0, contradicting the prediction — weight should decrease
        let bp = mixer.bit_position;
        let before = mixer.weights[0][bp];
        mixer.observe(0, &predictions);
        let after = mixer.weights[0][bp];

        assert!(
            after < before,
            "weight should decrease when prediction is wrong: before={before}, after={after}"
        );
    }

    fn roundtrip_order8(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order8(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order8(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order16(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order16(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order16(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order32(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order32(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order32(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order64(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order64(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order64(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_mix(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_mix(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_mix(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
