use std::collections::HashMap;
use std::io::{self, Read, Write};

const MAGIC_ORDER1: &[u8; 4] = b"PPM1";
const MAGIC_ORDER2: &[u8; 4] = b"PPM2";
const MAGIC_ORDER3: &[u8; 4] = b"PPM3";
const MAGIC_LEGACY: &[u8; 4] = b"PPM0";
const SYMBOLS: usize = 256;
const MAX_ORDER: usize = 3;
const MAX_CONTEXT_TOTAL: u32 = 1 << 15;
const STATE_BITS: u32 = 32;
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

pub fn compress_order1<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER1, 1)
}

pub fn compress_order2<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER2, 2)
}

pub fn compress_order3<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    compress_with_order(input, output, MAGIC_ORDER3, 3)
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

    for (index, &symbol) in data.iter().enumerate() {
        let history = build_history(&data[..index], max_order);
        model.encode_symbol(symbol, &history, max_order, &mut encoder)?;
        model.observe(symbol, &history, max_order);
    }

    let payload = encoder.finish()?;
    output.write_all(&payload)?;
    Ok(())
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

pub fn decompress_legacy_order3<R: Read, W: Write>(input: R, output: W) -> io::Result<()> {
    decompress_with_order(input, output, MAGIC_LEGACY, 3)
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
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let history = build_history(&restored, max_order);
        let symbol = model.decode_symbol(&history, max_order, &mut decoder)?;
        restored.push(symbol);
        model.observe(symbol, &history, max_order);
    }

    output.write_all(&restored)?;
    Ok(())
}

struct Model {
    order0: Context,
    order1: HashMap<u8, Context>,
    order2: HashMap<u16, Context>,
    order3: HashMap<u32, Context>,
}

impl Model {
    fn new() -> Self {
        Self {
            order0: Context::new(),
            order1: HashMap::new(),
            order2: HashMap::new(),
            order3: HashMap::new(),
        }
    }

    fn encode_symbol(
        &self,
        symbol: u8,
        history: &[u8],
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
            self.order0.encode_symbol(symbol, encoder)?;
        } else {
            self.order0.encode_escape(encoder)?;
            encoder.encode(symbol as u32, 1, SYMBOLS as u32)?;
        }

        Ok(())
    }

    fn decode_symbol(
        &self,
        history: &[u8],
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
            return Ok(symbol);
        }

        let value = decoder.target(SYMBOLS as u32)?;
        decoder.consume(value, 1, SYMBOLS as u32)?;
        Ok(value as u8)
    }

    fn observe(&mut self, symbol: u8, history: &[u8], max_order: usize) {
        self.order0.observe(symbol);

        for order in 1..=history.len().min(max_order) {
            match order {
                1 => self
                    .order1
                    .entry(history[0])
                    .or_insert_with(Context::new)
                    .observe(symbol),
                2 => self
                    .order2
                    .entry(order2_key(history))
                    .or_insert_with(Context::new)
                    .observe(symbol),
                3 => self
                    .order3
                    .entry(order3_key(history))
                    .or_insert_with(Context::new)
                    .observe(symbol),
                _ => unreachable!("unsupported ppm order"),
            }
        }
    }

    fn context_for_order(&self, order: usize, history: &[u8]) -> Option<&Context> {
        match order {
            1 => self.order1.get(&history[0]),
            2 => self.order2.get(&order2_key(history)),
            3 => self.order3.get(&order3_key(history)),
            _ => None,
        }
    }
}

fn build_history(data: &[u8], max_order: usize) -> Vec<u8> {
    data.iter()
        .rev()
        .copied()
        .take(max_order.min(MAX_ORDER))
        .collect()
}

fn order2_key(history: &[u8]) -> u16 {
    ((history[1] as u16) << 8) | history[0] as u16
}

fn order3_key(history: &[u8]) -> u32 {
    ((history[2] as u32) << 16) | ((history[1] as u32) << 8) | history[0] as u32
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
        let cum = self.cumulative(symbol);
        let freq = u32::from(
            self.find(symbol)
                .map(|index| self.counts[index].count)
                .unwrap_or(0),
        );
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

        let (symbol, cum, freq) = self.lookup(value)?;
        decoder.consume(cum, freq, total)?;
        Ok(Some(symbol))
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

    fn cumulative(&self, symbol: u8) -> u32 {
        self.counts
            .iter()
            .take_while(|entry| entry.symbol < symbol)
            .map(|entry| u32::from(entry.count))
            .sum()
    }

    fn lookup(&self, target: u32) -> io::Result<(u8, u32, u32)> {
        let mut cum = 0u32;
        for entry in &self.counts {
            let freq = u32::from(entry.count);
            if target < cum + freq {
                return Ok((entry.symbol, cum, freq));
            }
            cum += freq;
        }

        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "ppm symbol target out of range",
        ))
    }

    fn escape_freq(&self) -> u32 {
        (self.counts.len() as u32).max(1)
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
    use super::{
        compress_order1, compress_order2, compress_order3, decompress_order1, decompress_order2,
        decompress_order3,
    };

    #[test]
    fn roundtrip_repeated_text_all_orders() {
        let input = b"banana bandana banana bandana banana bandana";
        roundtrip_order1(input);
        roundtrip_order2(input);
        roundtrip_order3(input);
    }

    #[test]
    fn roundtrip_binary_all_orders() {
        let input: Vec<u8> = (0..=255).cycle().take(4096).collect();
        roundtrip_order1(&input);
        roundtrip_order2(&input);
        roundtrip_order3(&input);
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
}
