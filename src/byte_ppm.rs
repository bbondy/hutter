use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC_ORDER1: &[u8; 4] = b"PP11";
const MAGIC_ORDER2: &[u8; 4] = b"PP12";
const MAGIC_ORDER3: &[u8; 4] = b"PP13";
const MAGIC_ORDER4: &[u8; 4] = b"PP14";
const MAGIC_ORDER5: &[u8; 4] = b"PP15";
const MAGIC_ORDER6: &[u8; 4] = b"PP16";
const MAGIC_MIX: &[u8; 4] = b"PPMX";
const MAX_ORDER: usize = 6;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const MIX_LEARNING_RATE: f64 = 0.2;
const MIX_INITIAL_WEIGHTS: [f64; MAX_ORDER + 1] = [0.3, 0.5, 0.7, 1.0, 1.4, 1.9, 2.5];
const MIX_SCALE: f64 = 16384.0;
const MIX_ESCAPE_FREQ: u32 = 32;
const STATE_BITS: u32 = 32;
const SYMBOLS: u32 = 256;
const MAX_RANGE: u64 = (1u64 << STATE_BITS) - 1;
const HALF: u64 = 1u64 << (STATE_BITS - 1);
const QUARTER: u64 = HALF >> 1;
const THREE_QUARTERS: u64 = HALF + QUARTER;

pub fn magic_order1() -> &'static [u8; 4] {
    MAGIC_ORDER1
}

pub fn magic_order2() -> &'static [u8; 4] {
    MAGIC_ORDER2
}

pub fn magic_order3() -> &'static [u8; 4] {
    MAGIC_ORDER3
}

pub fn magic_order4() -> &'static [u8; 4] {
    MAGIC_ORDER4
}

pub fn magic_order5() -> &'static [u8; 4] {
    MAGIC_ORDER5
}

pub fn magic_order6() -> &'static [u8; 4] {
    MAGIC_ORDER6
}

pub fn magic_mix() -> &'static [u8; 4] {
    MAGIC_MIX
}

pub fn compress_order1<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER1, 1)
}

pub fn compress_order2<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER2, 2)
}

pub fn compress_order3<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER3, 3)
}

pub fn compress_order4<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER4, 4)
}

pub fn compress_order5<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER5, 5)
}

pub fn compress_order6<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER6, 6)
}

pub fn compress_mix<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_mixer(input, output, MAGIC_MIX, MAX_ORDER)
}

pub fn decompress_order1<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER1, 1)
}

pub fn decompress_order2<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER2, 2)
}

pub fn decompress_order3<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER3, 3)
}

pub fn decompress_order4<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER4, 4)
}

pub fn decompress_order5<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER5, 5)
}

pub fn decompress_order6<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_ORDER6, 6)
}

pub fn decompress_mix<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_mixer(input, output, MAGIC_MIX, MAX_ORDER)
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
    let mut history = ByteHistory::new(max_order);

    for &symbol in &data {
        model.encode_symbol(symbol, &history, max_order, &mut encoder)?;
        model.observe(symbol, &history, max_order);
        history.push(symbol);
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
    let mut history = ByteHistory::new(max_order);

    for &symbol in &data {
        model.encode_symbol(symbol, &history, &mut encoder)?;
        model.observe(symbol, &history);
        history.push(symbol);
    }

    output.write_all(&encoder.finish()?)?;
    Ok(())
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
    let mut history = ByteHistory::new(max_order);
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let symbol = model.decode_symbol(&history, max_order, &mut decoder)?;
        restored.push(symbol);
        model.observe(symbol, &history, max_order);
        history.push(symbol);
    }

    output.write_all(&restored)?;
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
    let mut history = ByteHistory::new(max_order);
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let symbol = model.decode_symbol(&history, &mut decoder)?;
        restored.push(symbol);
        model.observe(symbol, &history);
        history.push(symbol);
    }

    output.write_all(&restored)?;
    Ok(())
}

struct Model {
    order0: Context,
    contexts: Vec<HashMap<u64, Context>>,
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
        history: &ByteHistory,
        max_order: usize,
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        for order in (1..=history.len().min(max_order)).rev() {
            if let Some(context) = self.context_for_order(order, history) {
                if context.contains(symbol) {
                    return context.encode_symbol(symbol, encoder);
                }
                context.encode_escape(encoder)?;
            }
        }

        if self.order0.contains(symbol) {
            self.order0.encode_symbol(symbol, encoder)
        } else {
            self.order0.encode_escape(encoder)?;
            encoder.encode(u32::from(symbol), 1, SYMBOLS)
        }
    }

    fn decode_symbol(
        &self,
        history: &ByteHistory,
        max_order: usize,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        for order in (1..=history.len().min(max_order)).rev() {
            if let Some(context) = self.context_for_order(order, history) {
                if let Some(symbol) = context.decode_symbol(decoder)? {
                    return Ok(symbol);
                }
            }
        }

        if let Some(symbol) = self.order0.decode_symbol(decoder)? {
            Ok(symbol)
        } else {
            let value = decoder.target(SYMBOLS)?;
            decoder.consume(value, 1, SYMBOLS)?;
            Ok(value as u8)
        }
    }

    fn observe(&mut self, symbol: u8, history: &ByteHistory, max_order: usize) {
        self.order0.observe(symbol);

        for order in 1..=history.len().min(max_order) {
            self.contexts[order - 1]
                .entry(history.key(order))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }

    fn context_for_order(&self, order: usize, history: &ByteHistory) -> Option<&Context> {
        self.contexts
            .get(order - 1)
            .and_then(|contexts| contexts.get(&history.key(order)))
    }
}

struct MixedModel {
    order0: Context,
    contexts: Vec<HashMap<u64, Context>>,
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
        history: &ByteHistory,
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        let candidates = self.mixed_candidates(history);
        encode_mixed_symbol(symbol, &candidates, encoder)
    }

    fn decode_symbol(
        &self,
        history: &ByteHistory,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        let candidates = self.mixed_candidates(history);
        decode_mixed_symbol(&candidates, decoder)
    }

    fn observe(&mut self, symbol: u8, history: &ByteHistory) {
        self.mixer.observe(symbol, &self.predictions(history));
        self.order0.observe(symbol);

        for order in 1..=history.len().min(self.max_order) {
            self.contexts[order - 1]
                .entry(history.key(order))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }

    fn mixed_candidates(&self, history: &ByteHistory) -> Vec<WeightedSymbol> {
        self.mixer.combine(&self.predictions(history))
    }

    fn predictions(&self, history: &ByteHistory) -> Vec<OrderPrediction> {
        let mut predictions = Vec::with_capacity(self.max_order + 1);
        predictions.push(OrderPrediction {
            order: 0,
            symbols: self.order0.symbols(),
        });

        for order in 1..=history.len().min(self.max_order) {
            let context = self.contexts[order - 1].get(&history.key(order));
            predictions.push(OrderPrediction {
                order,
                symbols: context.map(Context::symbols).unwrap_or_default(),
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
    weights: Vec<f64>,
}

impl OrderMixer {
    fn new(max_order: usize) -> Self {
        let weights = (0..=max_order)
            .map(|order| {
                if order < MIX_INITIAL_WEIGHTS.len() {
                    MIX_INITIAL_WEIGHTS[order]
                } else {
                    *MIX_INITIAL_WEIGHTS.last().unwrap()
                }
            })
            .collect();
        Self { weights }
    }

    fn combine(&self, predictions: &[OrderPrediction]) -> Vec<WeightedSymbol> {
        let mut scores = HashMap::<u8, f64>::new();

        for prediction in predictions {
            let total = prediction_total(prediction);
            if total == 0.0 {
                continue;
            }

            for &(symbol, count) in &prediction.symbols {
                let probability = (f64::from(count) + 0.5) / (total + 0.5 * f64::from(SYMBOLS));
                *scores.entry(symbol).or_insert(0.0) +=
                    self.weights[prediction.order] * probability;
            }
        }

        if scores.is_empty() {
            return Vec::new();
        }

        let mut candidates: Vec<_> = scores
            .into_iter()
            .filter_map(|(symbol, score)| {
                let weight = (score * MIX_SCALE).round() as u32;
                (weight > 0).then_some(WeightedSymbol { symbol, weight })
            })
            .collect();
        candidates.sort_by_key(|candidate| candidate.symbol);
        candidates
    }

    fn observe(&mut self, symbol: u8, predictions: &[OrderPrediction]) {
        let mixed = self.symbol_probability(symbol, predictions);
        for prediction in predictions {
            let total = prediction_total(prediction);
            if total == 0.0 {
                continue;
            }

            let own = prediction_symbol_probability(prediction, symbol);
            self.weights[prediction.order] += MIX_LEARNING_RATE * (own - mixed);
            self.weights[prediction.order] = self.weights[prediction.order].clamp(0.05, 8.0);
        }
    }

    fn symbol_probability(&self, symbol: u8, predictions: &[OrderPrediction]) -> f64 {
        let mut weighted_sum = 0.0;
        let mut total_weight = 0.0;

        for prediction in predictions {
            let total = prediction_total(prediction);
            if total == 0.0 {
                continue;
            }

            weighted_sum +=
                self.weights[prediction.order] * prediction_symbol_probability(prediction, symbol);
            total_weight += self.weights[prediction.order];
        }

        if total_weight == 0.0 {
            1.0 / f64::from(SYMBOLS)
        } else {
            weighted_sum / total_weight
        }
    }
}

fn prediction_total(prediction: &OrderPrediction) -> f64 {
    prediction
        .symbols
        .iter()
        .map(|&(_, count)| f64::from(count))
        .sum()
}

fn prediction_symbol_probability(prediction: &OrderPrediction, symbol: u8) -> f64 {
    let total = prediction_total(prediction);
    if total == 0.0 {
        return 1.0 / f64::from(SYMBOLS);
    }

    let count = prediction
        .symbols
        .iter()
        .find_map(|&(candidate, count)| (candidate == symbol).then_some(count))
        .unwrap_or(0);
    (f64::from(count) + 0.5) / (total + 0.5 * f64::from(SYMBOLS))
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

impl Context {
    fn new() -> Self {
        Self {
            counts: Vec::new(),
            total: 0,
        }
    }

    fn contains(&self, symbol: u8) -> bool {
        self.find(symbol).is_some()
    }

    fn encode_symbol(&self, symbol: u8, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
        let Some(index) = self.find(symbol) else {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "symbol missing from context",
            ));
        };

        let cum: u32 = self.counts[..index]
            .iter()
            .map(|entry| u32::from(entry.count))
            .sum();
        encoder.encode(
            cum,
            u32::from(self.counts[index].count),
            self.total_with_escape(),
        )
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

        let mut cum = 0u32;
        for entry in &self.counts {
            let freq = u32::from(entry.count);
            if value < cum + freq {
                decoder.consume(cum, freq, total)?;
                return Ok(Some(entry.symbol));
            }
            cum += freq;
        }

        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "decoded symbol outside context range",
        ))
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

    fn escape_freq(&self) -> u32 {
        self.counts.len().max(1) as u32
    }

    fn total_with_escape(&self) -> u32 {
        self.total + self.escape_freq()
    }

    fn rescale(&mut self) {
        self.total = 0;
        for entry in &mut self.counts {
            entry.count = entry.count.div_ceil(2).max(1);
            self.total += u32::from(entry.count);
        }
    }

    fn find(&self, symbol: u8) -> Option<usize> {
        self.counts
            .binary_search_by_key(&symbol, |entry| entry.symbol)
            .ok()
    }

    fn symbols(&self) -> Vec<(u8, u32)> {
        self.counts
            .iter()
            .map(|entry| (entry.symbol, u32::from(entry.count)))
            .collect()
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
    encoder.encode(u32::from(symbol), 1, SYMBOLS)
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
    let value = decoder.target(SYMBOLS)?;
    decoder.consume(value, 1, SYMBOLS)?;
    Ok(value as u8)
}

fn mixed_total(candidates: &[WeightedSymbol]) -> u32 {
    candidates.iter().fold(MIX_ESCAPE_FREQ, |total, candidate| {
        total.saturating_add(candidate.weight)
    })
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
        compress_mix, compress_order1, compress_order2, compress_order3, compress_order4,
        compress_order5, compress_order6, decompress_mix, decompress_order1, decompress_order2,
        decompress_order3, decompress_order4, decompress_order5, decompress_order6,
    };

    #[test]
    fn roundtrip_all_orders() {
        let input = b"banana bandana banana bandana banana bandana";
        roundtrip_order1(input);
        roundtrip_order2(input);
        roundtrip_order3(input);
        roundtrip_order4(input);
        roundtrip_order5(input);
        roundtrip_order6(input);
        roundtrip_mix(input);
    }

    #[test]
    fn roundtrip_binary() {
        let input: Vec<u8> = (0..=255).cycle().take(4096).collect();
        roundtrip_order3(&input);
        roundtrip_order6(&input);
        roundtrip_mix(&input);
    }

    #[test]
    fn order6_differs_from_order1_on_structured_input() {
        let input = b"abc123abc123abc123abc123abc123abc123";

        let mut compressed1 = Vec::new();
        compress_order1(&input[..], &mut compressed1).unwrap();

        let mut compressed6 = Vec::new();
        compress_order6(&input[..], &mut compressed6).unwrap();

        assert_ne!(compressed1, compressed6);
    }

    #[test]
    fn mix_roundtrip_empty() {
        roundtrip_mix(b"");
    }

    fn roundtrip_order1(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order1(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order1(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order2(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order2(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order2(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order3(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order3(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order3(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order4(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order4(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order4(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order5(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order5(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order5(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_order6(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_order6(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_order6(&compressed[..], &mut restored).unwrap();
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
