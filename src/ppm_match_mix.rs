use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"PMM2";
const MAGIC_MATCH_ONLY: &[u8; 4] = b"PMAT";
const MATCH_BYTE_MARKER: &[u8; 4] = b"MBY1";
const BIT_MAX_ORDER: usize = 64;
const BYTE_MAX_ORDER: usize = 6;
const MATCH_HASH_LEN: usize = 4;
const MATCH_MAX_CANDIDATES: usize = 8;
const MATCH_WINDOW: usize = 1 << 15;
const MATCH_MAX_LOOKAHEAD: usize = 64;
const MATCH_ESCAPE_WEIGHT: u32 = 16;
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

pub fn magic_match_only() -> &'static [u8; 4] {
    MAGIC_MATCH_ONLY
}

pub fn compress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    compress_with_config(
        &mut input,
        &mut output,
        MAGIC,
        ModelConfig::new(true, true, true),
    )
}

pub fn compress_match_only<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(MAGIC_MATCH_ONLY)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;
    output.write_all(MATCH_BYTE_MARKER)?;

    let mut model = MatchModel::new(MATCH_WINDOW, MATCH_HASH_LEN, MATCH_MAX_CANDIDATES);
    let mut encoder = ArithmeticEncoder::new();

    for &byte in &data {
        model.encode_byte(byte, &mut encoder)?;
        model.observe(byte);
    }

    output.write_all(&encoder.finish()?)?;
    Ok(())
}

fn compress_with_config<R: Read, W: Write>(
    mut input: R,
    mut output: W,
    magic: &[u8; 4],
    config: ModelConfig,
) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(magic)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut model = HybridModel::new(BIT_MAX_ORDER, BYTE_MAX_ORDER, config);
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
    decompress_with_config(
        &mut input,
        &mut output,
        MAGIC,
        ModelConfig::new(true, true, true),
    )
}

pub fn decompress_match_only<R: Read, W: Write>(mut input: R, output: W) -> io::Result<()> {
    let mut magic = [0u8; 4];
    input.read_exact(&mut magic)?;
    if &magic != MAGIC_MATCH_ONLY {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid archive magic",
        ));
    }

    let original_size = read_u64(&mut input)? as usize;
    let mut payload = Vec::new();
    input.read_to_end(&mut payload)?;

    if payload.starts_with(MATCH_BYTE_MARKER) {
        return decompress_match_only_byte(
            &payload[MATCH_BYTE_MARKER.len()..],
            original_size,
            output,
        );
    }

    decompress_match_only_legacy(&payload, original_size, output)
}

fn decompress_match_only_byte<W: Write>(
    payload: &[u8],
    original_size: usize,
    mut output: W,
) -> io::Result<()> {
    let mut model = MatchModel::new(MATCH_WINDOW, MATCH_HASH_LEN, MATCH_MAX_CANDIDATES);
    let mut decoder = ArithmeticDecoder::new(payload)?;
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let byte = model.decode_byte(&mut decoder)?;
        restored.push(byte);
        model.observe(byte);
    }

    output.write_all(&restored)?;
    Ok(())
}

fn decompress_match_only_legacy<W: Write>(
    payload: &[u8],
    original_size: usize,
    mut output: W,
) -> io::Result<()> {
    let mut model = HybridModel::new(
        BIT_MAX_ORDER,
        BYTE_MAX_ORDER,
        ModelConfig::new(false, false, true),
    );
    let mut decoder = ArithmeticDecoder::new(payload)?;
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

fn decompress_with_config<R: Read, W: Write>(
    mut input: R,
    mut output: W,
    expected_magic: &[u8; 4],
    config: ModelConfig,
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

    let mut model = HybridModel::new(BIT_MAX_ORDER, BYTE_MAX_ORDER, config);
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

#[derive(Clone, Copy)]
struct ModelConfig {
    use_bit_model: bool,
    use_byte_model: bool,
    use_match_model: bool,
}

impl ModelConfig {
    const fn new(use_bit_model: bool, use_byte_model: bool, use_match_model: bool) -> Self {
        Self {
            use_bit_model,
            use_byte_model,
            use_match_model,
        }
    }
}

struct HybridModel {
    bit_order0: BitContext,
    bit_contexts: Vec<HashMap<u64, BitContext>>,
    byte_order0: ByteContext,
    byte_contexts: Vec<HashMap<u64, ByteContext>>,
    match_model: MatchModel,
    mixer: HybridMixer,
    bit_history: BitHistory,
    byte_history: ByteHistory,
    current_byte: u8,
    used_bits: u8,
    bit_max_order: usize,
    byte_max_order: usize,
    config: ModelConfig,
}

impl HybridModel {
    fn new(bit_max_order: usize, byte_max_order: usize, config: ModelConfig) -> Self {
        Self {
            bit_order0: BitContext::new(),
            bit_contexts: (0..bit_max_order).map(|_| HashMap::new()).collect(),
            byte_order0: ByteContext::new(),
            byte_contexts: (0..byte_max_order).map(|_| HashMap::new()).collect(),
            match_model: MatchModel::new(MATCH_WINDOW, MATCH_HASH_LEN, MATCH_MAX_CANDIDATES),
            mixer: HybridMixer::new(bit_max_order, byte_max_order),
            bit_history: BitHistory::new(bit_max_order),
            byte_history: ByteHistory::new(byte_max_order),
            current_byte: 0,
            used_bits: 0,
            bit_max_order,
            byte_max_order,
            config,
        }
    }

    fn encode_bit(
        &self,
        bit: u8,
        predictions: &Predictions,
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        let p1 = self.mixed_probability(predictions);
        encode_probability(bit, p1, encoder)
    }

    fn decode_bit(
        &self,
        predictions: &Predictions,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        let p1 = self.mixed_probability(predictions);
        decode_probability(p1, decoder)
    }

    fn observe_bit(&mut self, bit: u8, predictions: &Predictions) {
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
            self.match_model.observe(byte);
            self.current_byte = 0;
            self.used_bits = 0;
        }
    }

    fn mixed_probability(&self, predictions: &Predictions) -> f64 {
        self.mixer.mixed_probability(&predictions)
    }

    fn predictions(&self) -> Predictions {
        let mut bit_predictions = Vec::with_capacity(self.bit_max_order + 1);
        bit_predictions.push(OrderProbability {
            order: 0,
            p1: if self.config.use_bit_model {
                self.bit_order0.probability()
            } else {
                None
            },
        });
        for order in 1..=self.bit_history.len().min(self.bit_max_order) {
            bit_predictions.push(OrderProbability {
                order,
                p1: if self.config.use_bit_model {
                    self.bit_contexts[order - 1]
                        .get(&self.bit_history.key(order))
                        .and_then(BitContext::probability)
                } else {
                    None
                },
            });
        }

        let mut byte_predictions = Vec::with_capacity(self.byte_max_order + 1);
        byte_predictions.push(OrderProbability {
            order: 0,
            p1: if self.config.use_byte_model {
                self.byte_order0
                    .bit_probability(self.current_byte, self.used_bits)
            } else {
                None
            },
        });
        for order in 1..=self.byte_history.len().min(self.byte_max_order) {
            byte_predictions.push(OrderProbability {
                order,
                p1: if self.config.use_byte_model {
                    self.byte_contexts[order - 1]
                        .get(&self.byte_history.key(order))
                        .and_then(|ctx| ctx.bit_probability(self.current_byte, self.used_bits))
                } else {
                    None
                },
            });
        }

        Predictions {
            bit: bit_predictions,
            byte: byte_predictions,
            match_p1: if self.config.use_match_model {
                self.match_model
                    .bit_probability(self.current_byte, self.used_bits)
            } else {
                None
            },
        }
    }
}

struct Predictions {
    bit: Vec<OrderProbability>,
    byte: Vec<OrderProbability>,
    match_p1: Option<f64>,
}

#[derive(Clone, Copy)]
struct OrderProbability {
    order: usize,
    p1: Option<f64>,
}

struct HybridMixer {
    bit_weights: Vec<[f64; 8]>,
    byte_weights: Vec<[f64; 8]>,
    match_weight: [f64; 8],
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
            match_weight: [match_initial_weight(); 8],
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
        if let Some(p1) = predictions.match_p1 {
            logit_sum += self.match_weight[bp] * stretch(p1);
            any_context = true;
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
        if let Some(p1) = predictions.match_p1 {
            self.match_weight[bp] += MIX_LEARNING_RATE * error * stretch(p1);
            self.match_weight[bp] = self.match_weight[bp].clamp(-6.0, 6.0);
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

fn match_initial_weight() -> f64 {
    2.4
}

struct MatchModel {
    data: Vec<u8>,
    positions: HashMap<u32, VecDeque<usize>>,
    window: usize,
    hash_len: usize,
    max_candidates: usize,
    cached_candidates: Vec<MatchCandidate>,
    cached_symbols: Vec<WeightedSymbol>,
}

impl MatchModel {
    fn new(window: usize, hash_len: usize, max_candidates: usize) -> Self {
        Self {
            data: Vec::new(),
            positions: HashMap::new(),
            window,
            hash_len,
            max_candidates,
            cached_candidates: Vec::with_capacity(max_candidates),
            cached_symbols: Vec::with_capacity(max_candidates),
        }
    }

    fn observe(&mut self, byte: u8) {
        self.data.push(byte);
        if self.data.len() < self.hash_len {
            return;
        }

        let position = self.data.len() - self.hash_len;
        let key = match_key_at(&self.data, position, self.hash_len);
        let entry = self.positions.entry(key).or_default();
        entry.push_back(position);

        while entry.len() > self.max_candidates {
            entry.pop_front();
        }

        while let Some(&oldest) = entry.front() {
            if position.saturating_sub(oldest) <= self.window {
                break;
            }
            entry.pop_front();
        }

        self.refresh_candidates();
    }

    fn bit_probability(&self, prefix: u8, used_bits: u8) -> Option<f64> {
        if self.cached_candidates.is_empty() {
            return None;
        }

        let mut count0 = 0.0;
        let mut count1 = 0.0;

        for candidate in &self.cached_candidates {
            if !byte_matches_prefix(candidate.symbol, prefix, used_bits) {
                continue;
            }

            if next_bit(candidate.symbol, used_bits) == 0 {
                count0 += f64::from(candidate.weight);
            } else {
                count1 += f64::from(candidate.weight);
            }
        }

        let total = count0 + count1;
        if total == 0.0 {
            None
        } else {
            Some((count1 + 0.5) / (total + 1.0))
        }
    }

    fn encode_byte(&self, byte: u8, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
        let predicted_total = self.predicted_total();
        if let Some((cum, freq, total)) = self.predicted_byte_range(byte) {
            encoder.encode(MATCH_ESCAPE_WEIGHT, total - MATCH_ESCAPE_WEIGHT, total)?;
            encoder.encode(cum, freq, total - MATCH_ESCAPE_WEIGHT)
        } else {
            let total = MATCH_ESCAPE_WEIGHT + predicted_total;
            encoder.encode(0, MATCH_ESCAPE_WEIGHT, total)?;
            encoder.encode(u32::from(byte), 1, 256)
        }
    }

    fn decode_byte(&self, decoder: &mut ArithmeticDecoder<'_>) -> io::Result<u8> {
        let predicted_total = self.predicted_total();
        let total = MATCH_ESCAPE_WEIGHT + predicted_total;
        let target = decoder.target(total)?;
        if target < MATCH_ESCAPE_WEIGHT {
            decoder.consume(0, MATCH_ESCAPE_WEIGHT, total)?;
            let symbol = decoder.target(256)?;
            decoder.consume(symbol, 1, 256)?;
            Ok(symbol as u8)
        } else {
            decoder.consume(MATCH_ESCAPE_WEIGHT, predicted_total, total)?;
            let symbol_target = decoder.target(predicted_total)?;
            let mut cum = 0u32;
            for symbol in &self.cached_symbols {
                let next = cum + symbol.weight;
                if symbol_target < next {
                    decoder.consume(cum, symbol.weight, predicted_total)?;
                    return Ok(symbol.symbol);
                }
                cum = next;
            }

            Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "predicted symbol target out of range",
            ))
        }
    }

    fn predicted_byte_range(&self, byte: u8) -> Option<(u32, u32, u32)> {
        if self.cached_symbols.is_empty() {
            return None;
        }

        let mut cum = 0u32;
        for symbol in &self.cached_symbols {
            if symbol.symbol == byte {
                let total = MATCH_ESCAPE_WEIGHT + self.predicted_total();
                return Some((cum, symbol.weight, total));
            }
            cum += symbol.weight;
        }
        None
    }

    fn predicted_total(&self) -> u32 {
        self.cached_symbols.iter().map(|symbol| symbol.weight).sum()
    }

    fn refresh_candidates(&mut self) {
        self.cached_candidates.clear();
        self.cached_symbols.clear();
        if self.data.len() < self.hash_len {
            return;
        }

        let suffix_start = self.data.len() - self.hash_len;
        let key = match_key_at(&self.data, suffix_start, self.hash_len);
        let Some(positions) = self.positions.get(&key) else {
            return;
        };

        for &candidate in positions.iter().rev() {
            if candidate >= suffix_start {
                continue;
            }

            let distance = suffix_start - candidate;
            if distance == 0 || distance > self.window {
                continue;
            }

            let length = match_length(&self.data, candidate, suffix_start);
            if length < self.hash_len {
                continue;
            }

            self.cached_candidates.push(MatchCandidate {
                symbol: self.data[candidate + (length % distance)],
                weight: match_weight(length, distance),
            });
        }

        for candidate in &self.cached_candidates {
            if let Some(existing) = self
                .cached_symbols
                .iter_mut()
                .find(|symbol| symbol.symbol == candidate.symbol)
            {
                existing.weight = existing.weight.saturating_add(candidate.weight);
            } else {
                self.cached_symbols.push(WeightedSymbol {
                    symbol: candidate.symbol,
                    weight: candidate.weight,
                });
            }
        }
    }
}

struct WeightedSymbol {
    symbol: u8,
    weight: u32,
}

struct MatchCandidate {
    symbol: u8,
    weight: u32,
}

fn match_weight(length: usize, distance: usize) -> u32 {
    let length_score = (length.saturating_sub(MATCH_HASH_LEN) + 1).min(MATCH_MAX_LOOKAHEAD) as u32;
    let recency = match distance {
        1..=64 => 25,
        65..=512 => 18,
        513..=4096 => 13,
        _ => 9,
    };
    length_score.saturating_mul(recency)
}

fn match_length(data: &[u8], candidate: usize, current: usize) -> usize {
    let distance = current - candidate;
    let mut length = 0usize;

    while length < MATCH_MAX_LOOKAHEAD
        && current + length < data.len()
        && data[candidate + (length % distance)] == data[current + length]
    {
        length += 1;
    }

    length
}

fn match_key_at(data: &[u8], position: usize, len: usize) -> u32 {
    let mut key = 0x811c9dc5u32;
    for &byte in &data[position..position + len] {
        key ^= u32::from(byte);
        key = key.wrapping_mul(0x0100_0193);
    }
    key
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
    use super::{MatchModel, compress, compress_match_only, decompress, decompress_match_only};

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

    #[test]
    fn roundtrip_match_only_text() {
        roundtrip_match_only(b"banana bandana banana bandana");
    }

    #[test]
    fn match_model_predicts_repeated_continuation() {
        let mut model = MatchModel::new(1 << 15, 4, 8);
        for &byte in b"banana bandana banana bandan" {
            model.observe(byte);
        }

        let p1 = model.bit_probability(0, 0).unwrap();
        assert!(p1 > 0.0 && p1 < 1.0);
    }

    fn roundtrip(input: &[u8]) {
        let mut compressed = Vec::new();
        compress(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    fn roundtrip_match_only(input: &[u8]) {
        let mut compressed = Vec::new();
        compress_match_only(input, &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress_match_only(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
