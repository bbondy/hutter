use std::collections::{HashMap, VecDeque};
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"PPMD";
const MAX_ORDER: usize = 6;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const SYMBOLS: u32 = 256;
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

    let mut model = Model::new();
    let mut encoder = ArithmeticEncoder::new();
    let mut history = ByteHistory::new(MAX_ORDER);

    for &symbol in &data {
        model.encode_symbol(symbol, &history, &mut encoder)?;
        model.observe(symbol, &history);
        history.push(symbol);
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

    let mut model = Model::new();
    let mut decoder = ArithmeticDecoder::new(&payload)?;
    let mut history = ByteHistory::new(MAX_ORDER);
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
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        let mut excluded = [false; 256];

        for order in (1..=history.len().min(MAX_ORDER)).rev() {
            let Some(context) = self.context_for_order(order, history) else {
                continue;
            };
            let stats = context.stats(&excluded);
            if stats.symbols == 0 {
                continue;
            }

            if let Some((cum, freq, total)) =
                stats.symbol_range_with_context(context, symbol, &excluded)
            {
                encoder.encode(cum, freq, total)?;
                return Ok(());
            }

            encoder.encode(stats.total, stats.escape_freq, stats.total_with_escape())?;
            context.exclude_all(&mut excluded);
        }

        let stats = self.order0.stats(&excluded);
        if stats.symbols > 0 {
            if let Some((cum, freq, total)) =
                stats.symbol_range_with_context(&self.order0, symbol, &excluded)
            {
                encoder.encode(cum, freq, total)?;
                return Ok(());
            }

            encoder.encode(stats.total, stats.escape_freq, stats.total_with_escape())?;
            self.order0.exclude_all(&mut excluded);
        }

        encode_order_minus_one(symbol, &excluded, encoder)
    }

    fn decode_symbol(
        &self,
        history: &ByteHistory,
        decoder: &mut ArithmeticDecoder<'_>,
    ) -> io::Result<u8> {
        let mut excluded = [false; 256];

        for order in (1..=history.len().min(MAX_ORDER)).rev() {
            let Some(context) = self.context_for_order(order, history) else {
                continue;
            };
            let stats = context.stats(&excluded);
            if stats.symbols == 0 {
                continue;
            }

            let target = decoder.target(stats.total_with_escape())?;
            if target < stats.total {
                let (symbol, cum, freq) = context.decode_filtered_symbol(target, &excluded)?;
                decoder.consume(cum, freq, stats.total_with_escape())?;
                return Ok(symbol);
            }

            decoder.consume(stats.total, stats.escape_freq, stats.total_with_escape())?;
            context.exclude_all(&mut excluded);
        }

        let stats = self.order0.stats(&excluded);
        if stats.symbols > 0 {
            let target = decoder.target(stats.total_with_escape())?;
            if target < stats.total {
                let (symbol, cum, freq) = self.order0.decode_filtered_symbol(target, &excluded)?;
                decoder.consume(cum, freq, stats.total_with_escape())?;
                return Ok(symbol);
            }

            decoder.consume(stats.total, stats.escape_freq, stats.total_with_escape())?;
            self.order0.exclude_all(&mut excluded);
        }

        decode_order_minus_one(&excluded, decoder)
    }

    fn observe(&mut self, symbol: u8, history: &ByteHistory) {
        self.order0.observe(symbol);

        for order in 1..=history.len().min(MAX_ORDER) {
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
struct FilteredStats {
    total: u32,
    symbols: usize,
    escape_freq: u32,
}

impl FilteredStats {
    fn total_with_escape(self) -> u32 {
        self.total + self.escape_freq
    }
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

        FilteredStats {
            total,
            symbols,
            escape_freq,
        }
    }

    fn symbol_range(&self, symbol: u8, excluded: &[bool; 256]) -> Option<(u32, u32)> {
        let mut cum = 0u32;

        for entry in &self.counts {
            if excluded[entry.symbol as usize] {
                continue;
            }
            let freq = u32::from(entry.count);
            if entry.symbol == symbol {
                return Some((cum, freq));
            }
            cum += freq;
        }

        None
    }

    fn decode_filtered_symbol(
        &self,
        target: u32,
        excluded: &[bool; 256],
    ) -> io::Result<(u8, u32, u32)> {
        let mut cum = 0u32;

        for entry in &self.counts {
            if excluded[entry.symbol as usize] {
                continue;
            }
            let freq = u32::from(entry.count);
            if target < cum + freq {
                return Ok((entry.symbol, cum, freq));
            }
            cum += freq;
        }

        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "decoded symbol outside filtered context range",
        ))
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

impl FilteredStats {
    fn symbol_range_with_context(
        self,
        context: &Context,
        symbol: u8,
        excluded: &[bool; 256],
    ) -> Option<(u32, u32, u32)> {
        context
            .symbol_range(symbol, excluded)
            .map(|(cum, freq)| (cum, freq, self.total_with_escape()))
    }
}

fn encode_order_minus_one(
    symbol: u8,
    excluded: &[bool; 256],
    encoder: &mut ArithmeticEncoder,
) -> io::Result<()> {
    if excluded[symbol as usize] {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "symbol excluded at order -1",
        ));
    }

    let mut cum = 0u32;
    for candidate in 0..symbol {
        if !excluded[candidate as usize] {
            cum += 1;
        }
    }

    let total = SYMBOLS - excluded.iter().filter(|&&value| value).count() as u32;
    encoder.encode(cum, 1, total)
}

fn decode_order_minus_one(
    excluded: &[bool; 256],
    decoder: &mut ArithmeticDecoder<'_>,
) -> io::Result<u8> {
    let total = SYMBOLS - excluded.iter().filter(|&&value| value).count() as u32;
    let target = decoder.target(total)?;

    let mut cum = 0u32;
    for symbol in 0..=u8::MAX {
        if excluded[symbol as usize] {
            continue;
        }
        if target == cum {
            decoder.consume(cum, 1, total)?;
            return Ok(symbol);
        }
        cum += 1;
    }

    Err(io::Error::new(
        io::ErrorKind::InvalidData,
        "order -1 target out of range",
    ))
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
