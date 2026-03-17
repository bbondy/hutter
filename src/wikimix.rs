use std::array;
use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"WMX5";
const SYMBOLS: usize = 256;
const ESCAPE_FREQ: u32 = 32;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const MAX_ORDER: usize = 6;
const MATCH_KEY_LEN: usize = 4;
const MATCH_CANDIDATES: usize = 8;
const STATE_BITS: u32 = 32;
const MAX_RANGE: u64 = (1u64 << STATE_BITS) - 1;
const HALF: u64 = 1u64 << (STATE_BITS - 1);
const QUARTER: u64 = HALF >> 1;
const THREE_QUARTERS: u64 = HALF + QUARTER;
const MIXER_WEIGHTS: [u32; 5] = [14, 8, 5, 10, 6];

pub fn magic() -> &'static [u8; 4] {
    MAGIC
}

pub fn compress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(MAGIC)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut encoder = ArithmeticEncoder::new();
    let mut model = WikiMix5Model::new();

    for &symbol in &data {
        let candidates = model.predict();
        encode_symbol(symbol, &candidates, &mut encoder)?;
        model.observe(symbol);
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

    let mut decoder = ArithmeticDecoder::new(&payload)?;
    let mut model = WikiMix5Model::new();
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let candidates = model.predict();
        let symbol = decode_symbol(&candidates, &mut decoder)?;
        restored.push(symbol);
        model.observe(symbol);
    }

    output.write_all(&restored)?;
    Ok(())
}

fn encode_symbol(
    symbol: u8,
    candidates: &[WeightedSymbol],
    encoder: &mut ArithmeticEncoder,
) -> io::Result<()> {
    let total = candidate_total(candidates) + ESCAPE_FREQ;
    let mut cum = 0u32;

    for candidate in candidates {
        if candidate.symbol == symbol {
            return encoder.encode(cum, candidate.weight, total);
        }
        cum += candidate.weight;
    }

    encoder.encode(cum, ESCAPE_FREQ, total)?;
    encoder.encode(symbol as u32, 1, SYMBOLS as u32)
}

fn decode_symbol(
    candidates: &[WeightedSymbol],
    decoder: &mut ArithmeticDecoder<'_>,
) -> io::Result<u8> {
    let total = candidate_total(candidates) + ESCAPE_FREQ;
    let target = decoder.target(total)?;
    let mut cum = 0u32;

    for candidate in candidates {
        if target < cum + candidate.weight {
            decoder.consume(cum, candidate.weight, total)?;
            return Ok(candidate.symbol);
        }
        cum += candidate.weight;
    }

    decoder.consume(cum, ESCAPE_FREQ, total)?;
    let value = decoder.target(SYMBOLS as u32)?;
    decoder.consume(value, 1, SYMBOLS as u32)?;
    Ok(value as u8)
}

fn candidate_total(candidates: &[WeightedSymbol]) -> u32 {
    candidates.iter().map(|candidate| candidate.weight).sum()
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct WeightedSymbol {
    symbol: u8,
    weight: u32,
}

#[derive(Debug)]
struct WikiMix5Model {
    history: ByteHistory,
    byte_ppm: BytePpmModel,
    struct_state: StructStateModel,
    word: WordModel,
    matcher: MatchModel,
    class: ClassModel,
    mixer: Mixer,
}

impl WikiMix5Model {
    fn new() -> Self {
        Self {
            history: ByteHistory::new(MAX_ORDER.max(MATCH_KEY_LEN + 2)),
            byte_ppm: BytePpmModel::new(MAX_ORDER),
            struct_state: StructStateModel::new(),
            word: WordModel::new(3),
            matcher: MatchModel::new(1 << 16),
            class: ClassModel::new(),
            mixer: Mixer::new(MIXER_WEIGHTS),
        }
    }

    fn predict(&self) -> Vec<WeightedSymbol> {
        let state = self.struct_state.state();
        self.mixer.combine([
            self.byte_ppm.predict(&self.history),
            self.struct_state.predict(&self.history),
            self.word.predict(),
            self.matcher.predict(),
            self.class.predict(state),
        ])
    }

    fn observe(&mut self, symbol: u8) {
        let state_before = self.struct_state.state();
        self.byte_ppm.observe(&self.history, symbol);
        self.word.observe(symbol);
        self.matcher.observe(symbol);
        self.class.observe(state_before, symbol);
        self.struct_state.observe(&self.history, symbol);
        self.history.push(symbol);
    }
}

#[derive(Debug)]
struct ByteHistory {
    bytes: VecDeque<u8>,
    max_len: usize,
}

impl ByteHistory {
    fn new(max_len: usize) -> Self {
        Self {
            bytes: VecDeque::with_capacity(max_len),
            max_len,
        }
    }

    fn len(&self) -> usize {
        self.bytes.len()
    }

    fn recent(&self, order: usize) -> impl Iterator<Item = u8> + '_ {
        self.bytes.iter().rev().take(order).copied()
    }

    fn last(&self) -> Option<u8> {
        self.bytes.back().copied()
    }

    fn ends_with(&self, suffix: &[u8]) -> bool {
        if suffix.len() > self.bytes.len() {
            return false;
        }

        self.bytes
            .iter()
            .skip(self.bytes.len() - suffix.len())
            .copied()
            .eq(suffix.iter().copied())
    }

    fn push(&mut self, byte: u8) {
        if self.bytes.len() == self.max_len {
            self.bytes.pop_front();
        }
        self.bytes.push_back(byte);
    }
}

#[derive(Debug)]
struct BytePpmModel {
    order0: Context,
    contexts: Vec<HashMap<u64, Context>>,
    max_order: usize,
}

impl BytePpmModel {
    fn new(max_order: usize) -> Self {
        Self {
            order0: Context::new(),
            contexts: (0..max_order).map(|_| HashMap::new()).collect(),
            max_order,
        }
    }

    fn predict(&self, history: &ByteHistory) -> Vec<WeightedSymbol> {
        let mut predictions = Vec::new();

        for order in (1..=history.len().min(self.max_order)).rev() {
            if let Some(context) = self
                .contexts
                .get(order - 1)
                .and_then(|contexts| contexts.get(&order_key(history, order)))
            {
                add_predictions(
                    &mut predictions,
                    &context.top_symbols(3),
                    (order as u32) * 3 + 4,
                );
                break;
            }
        }

        add_predictions(&mut predictions, &self.order0.top_symbols(2), 2);
        predictions
    }

    fn observe(&mut self, history: &ByteHistory, symbol: u8) {
        self.order0.observe(symbol);

        for order in 1..=history.len().min(self.max_order) {
            self.contexts[order - 1]
                .entry(order_key(history, order))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SyntaxState {
    PlainText,
    XmlTag,
    WikiLink,
    Template,
    Table,
    Heading,
    Entity,
    Number,
    Utf8,
}

impl SyntaxState {
    fn index(self) -> usize {
        match self {
            Self::PlainText => 0,
            Self::XmlTag => 1,
            Self::WikiLink => 2,
            Self::Template => 3,
            Self::Table => 4,
            Self::Heading => 5,
            Self::Entity => 6,
            Self::Number => 7,
            Self::Utf8 => 8,
        }
    }
}

#[derive(Debug)]
struct StructStateModel {
    state: SyntaxState,
    counts: [Context; 9],
}

impl StructStateModel {
    fn new() -> Self {
        Self {
            state: SyntaxState::PlainText,
            counts: array::from_fn(|_| Context::new()),
        }
    }

    fn state(&self) -> SyntaxState {
        self.state
    }

    fn predict(&self, _history: &ByteHistory) -> Vec<WeightedSymbol> {
        let mut predictions = Vec::new();
        add_predictions(
            &mut predictions,
            &self.counts[self.state.index()].top_symbols(3),
            5,
        );
        predictions
    }

    fn observe(&mut self, history: &ByteHistory, byte: u8) {
        self.counts[self.state.index()].observe(byte);
        self.state = next_state(self.state, history, byte);
    }
}

#[derive(Debug)]
struct WordModel {
    contexts: HashMap<u64, Context>,
    recent_words: VecDeque<u64>,
    current_word: Vec<u8>,
    max_history: usize,
}

impl WordModel {
    fn new(max_history: usize) -> Self {
        Self {
            contexts: HashMap::new(),
            recent_words: VecDeque::with_capacity(max_history),
            current_word: Vec::new(),
            max_history,
        }
    }

    fn predict(&self) -> Vec<WeightedSymbol> {
        self.contexts
            .get(&self.context_key())
            .map(|context| {
                let mut predictions = Vec::new();
                add_predictions(&mut predictions, &context.top_symbols(2), 4);
                predictions
            })
            .unwrap_or_default()
    }

    fn observe(&mut self, byte: u8) {
        let key = self.context_key();
        self.contexts
            .entry(key)
            .or_insert_with(Context::new)
            .observe(byte);

        if byte.is_ascii_alphanumeric() {
            self.current_word.push(byte.to_ascii_lowercase());
            return;
        }

        if !self.current_word.is_empty() {
            let word_hash = hash_bytes(&self.current_word);
            if self.recent_words.len() == self.max_history {
                self.recent_words.pop_front();
            }
            self.recent_words.push_back(word_hash);
            self.current_word.clear();
        }
    }

    fn context_key(&self) -> u64 {
        let mut key = 0xcbf29ce484222325u64;
        for &word in &self.recent_words {
            key ^= word;
            key = key.wrapping_mul(0x100000001b3);
        }
        if !self.current_word.is_empty() {
            key ^= hash_bytes(&self.current_word);
            key = key.wrapping_mul(0x100000001b3);
        }
        key
    }
}

#[derive(Debug)]
struct MatchModel {
    data: Vec<u8>,
    positions: HashMap<u32, VecDeque<usize>>,
    window: usize,
}

impl MatchModel {
    fn new(window: usize) -> Self {
        Self {
            data: Vec::new(),
            positions: HashMap::new(),
            window,
        }
    }

    fn predict(&self) -> Vec<WeightedSymbol> {
        if self.data.len() < MATCH_KEY_LEN {
            return Vec::new();
        }

        let key = last_match_key(&self.data);
        let Some(positions) = self.positions.get(&key) else {
            return Vec::new();
        };

        let mut predictions = Vec::new();
        for &position in positions.iter().rev() {
            if position + MATCH_KEY_LEN >= self.data.len() {
                continue;
            }
            let distance = self.data.len() - position;
            let weight = if distance <= 64 {
                32
            } else if distance <= 512 {
                20
            } else {
                10
            };
            add_weight(
                &mut predictions,
                self.data[position + MATCH_KEY_LEN],
                weight,
            );
            if predictions.len() >= 2 {
                break;
            }
        }

        predictions
    }

    fn observe(&mut self, byte: u8) {
        self.data.push(byte);

        if self.data.len() < MATCH_KEY_LEN {
            return;
        }

        let position = self.data.len() - MATCH_KEY_LEN;
        let key = match_key_at(&self.data, position);
        let entry = self.positions.entry(key).or_default();
        entry.push_back(position);

        while entry.len() > MATCH_CANDIDATES {
            entry.pop_front();
        }

        while let Some(&oldest) = entry.front() {
            if position.saturating_sub(oldest) <= self.window {
                break;
            }
            entry.pop_front();
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SymbolClass {
    Plain,
    Digit,
    Delimiter,
    Entity,
    Utf8Lead,
    Utf8Continuation,
}

impl SymbolClass {
    fn index(self) -> usize {
        match self {
            Self::Plain => 0,
            Self::Digit => 1,
            Self::Delimiter => 2,
            Self::Entity => 3,
            Self::Utf8Lead => 4,
            Self::Utf8Continuation => 5,
        }
    }

    fn from_state(state: SyntaxState, byte: u8) -> Self {
        if matches!(state, SyntaxState::Entity) {
            return Self::Entity;
        }
        if byte.is_ascii_digit() {
            return Self::Digit;
        }
        if matches!(
            byte,
            b'<' | b'>' | b'[' | b']' | b'{' | b'}' | b'|' | b'=' | b'&'
        ) {
            return Self::Delimiter;
        }
        if byte & 0b1100_0000 == 0b1000_0000 {
            return Self::Utf8Continuation;
        }
        if byte & 0b1000_0000 != 0 {
            return Self::Utf8Lead;
        }
        Self::Plain
    }
}

#[derive(Debug)]
struct ClassModel {
    counts: [Context; 6],
}

impl ClassModel {
    fn new() -> Self {
        Self {
            counts: array::from_fn(|_| Context::new()),
        }
    }

    fn predict(&self, state: SyntaxState) -> Vec<WeightedSymbol> {
        let class = match state {
            SyntaxState::Entity => SymbolClass::Entity,
            SyntaxState::Number => SymbolClass::Digit,
            SyntaxState::Utf8 => SymbolClass::Utf8Lead,
            SyntaxState::XmlTag
            | SyntaxState::WikiLink
            | SyntaxState::Template
            | SyntaxState::Table
            | SyntaxState::Heading => SymbolClass::Delimiter,
            SyntaxState::PlainText => SymbolClass::Plain,
        };

        let mut predictions = Vec::new();
        add_predictions(
            &mut predictions,
            &self.counts[class.index()].top_symbols(2),
            4,
        );
        predictions
    }

    fn observe(&mut self, state: SyntaxState, byte: u8) {
        let class = SymbolClass::from_state(state, byte);
        self.counts[class.index()].observe(byte);
    }
}

#[derive(Debug)]
struct Mixer {
    weights: [u32; 5],
}

impl Mixer {
    fn new(weights: [u32; 5]) -> Self {
        Self { weights }
    }

    fn combine(&self, inputs: [Vec<WeightedSymbol>; 5]) -> Vec<WeightedSymbol> {
        let mut combined = Vec::new();

        for (index, predictions) in inputs.into_iter().enumerate() {
            let weight = self.weights[index];
            for prediction in predictions {
                add_weight(
                    &mut combined,
                    prediction.symbol,
                    prediction.weight.saturating_mul(weight),
                );
            }
        }

        combined.sort_by(|left, right| {
            right
                .weight
                .cmp(&left.weight)
                .then_with(|| left.symbol.cmp(&right.symbol))
        });
        combined.truncate(12);
        combined.sort_by_key(|candidate| candidate.symbol);
        combined
    }
}

#[derive(Debug)]
struct Context {
    counts: Vec<SymbolCount>,
    total: u32,
}

#[derive(Clone, Copy, Debug)]
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

    fn observe(&mut self, symbol: u8) {
        match self.find(symbol) {
            Some(index) => {
                let slot = &mut self.counts[index].count;
                *slot = slot.saturating_add(1);
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

    fn top_symbols(&self, limit: usize) -> Vec<(u8, u32)> {
        let mut top: Vec<(u8, u32)> = self
            .counts
            .iter()
            .map(|entry| (entry.symbol, u32::from(entry.count)))
            .collect();
        top.sort_by(|left, right| right.1.cmp(&left.1).then_with(|| left.0.cmp(&right.0)));
        top.truncate(limit);
        top
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
}

fn add_predictions(target: &mut Vec<WeightedSymbol>, source: &[(u8, u32)], bonus: u32) {
    for &(symbol, count) in source {
        add_weight(target, symbol, count.saturating_add(bonus));
    }
}

fn add_weight(target: &mut Vec<WeightedSymbol>, symbol: u8, weight: u32) {
    if weight == 0 {
        return;
    }

    if let Some(candidate) = target
        .iter_mut()
        .find(|candidate| candidate.symbol == symbol)
    {
        candidate.weight = candidate.weight.saturating_add(weight);
        return;
    }

    target.push(WeightedSymbol { symbol, weight });
}

fn next_state(current: SyntaxState, history: &ByteHistory, byte: u8) -> SyntaxState {
    match current {
        SyntaxState::XmlTag if byte == b'>' => SyntaxState::PlainText,
        SyntaxState::Entity if byte == b';' => SyntaxState::PlainText,
        SyntaxState::Heading if byte == b'\n' => SyntaxState::PlainText,
        SyntaxState::WikiLink if history.last() == Some(b']') && byte == b']' => {
            SyntaxState::PlainText
        }
        SyntaxState::Template if history.last() == Some(b'}') && byte == b'}' => {
            SyntaxState::PlainText
        }
        SyntaxState::Table if byte == b'\n' => SyntaxState::PlainText,
        _ => {
            if history.last() == Some(b'<') {
                SyntaxState::XmlTag
            } else if history.last() == Some(b'&') {
                SyntaxState::Entity
            } else if history.last() == Some(b'[') && byte == b'[' {
                SyntaxState::WikiLink
            } else if history.last() == Some(b'{') && byte == b'{' {
                SyntaxState::Template
            } else if history.last() == Some(b'{') && byte == b'|' {
                SyntaxState::Table
            } else if history.last() == Some(b'=') && byte == b'=' {
                SyntaxState::Heading
            } else if byte.is_ascii_digit()
                && matches!(current, SyntaxState::PlainText | SyntaxState::Number)
            {
                SyntaxState::Number
            } else if byte.is_ascii() {
                if history.ends_with(b"http:") || history.ends_with(b"www.") {
                    SyntaxState::WikiLink
                } else {
                    SyntaxState::PlainText
                }
            } else {
                SyntaxState::Utf8
            }
        }
    }
}

fn order_key(history: &ByteHistory, order: usize) -> u64 {
    let mut key = 0u64;
    for (shift, byte) in history.recent(order).enumerate() {
        key |= u64::from(byte) << (shift * 8);
    }
    key
}

fn hash_bytes(bytes: &[u8]) -> u64 {
    let mut hash = 0xcbf29ce484222325u64;
    for &byte in bytes {
        hash ^= u64::from(byte);
        hash = hash.wrapping_mul(0x100000001b3);
    }
    hash
}

fn match_key_at(data: &[u8], position: usize) -> u32 {
    let mut key = 0u32;
    for &byte in &data[position..position + MATCH_KEY_LEN] {
        key = (key << 8) | u32::from(byte);
    }
    key
}

fn last_match_key(data: &[u8]) -> u32 {
    match_key_at(data, data.len() - MATCH_KEY_LEN)
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
        if freq == 0 || cum + freq > total || total == 0 {
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
        if freq == 0 || cum + freq > total || total == 0 {
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
    use super::{compress, decompress};

    #[test]
    fn roundtrip_repeated_text() {
        let input = b"<page><title>banana</title>[[Category:Fruit]] banana banana</page>";
        let mut compressed = Vec::new();
        compress(&input[..], &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    #[test]
    fn roundtrip_binary() {
        let input: Vec<u8> = (0..=255).cycle().take(4096).collect();
        let mut compressed = Vec::new();
        compress(&input[..], &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
