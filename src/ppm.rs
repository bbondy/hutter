use std::collections::HashMap;
use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"PPM0";
const SYMBOLS: usize = 256;
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

    let mut model = Model::new();
    let mut encoder = ArithmeticEncoder::new();

    for (index, &symbol) in data.iter().enumerate() {
        let history = data[..index]
            .iter()
            .rev()
            .copied()
            .take(2)
            .collect::<Vec<_>>();
        model.encode_symbol(symbol, &history, &mut encoder)?;
        model.observe(symbol, &history);
    }

    let payload = encoder.finish()?;
    output.write_all(&payload)?;
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
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let history = restored.iter().rev().copied().take(2).collect::<Vec<_>>();
        let symbol = model.decode_symbol(&history, &mut decoder)?;
        restored.push(symbol);
        model.observe(symbol, &history);
    }

    output.write_all(&restored)?;
    Ok(())
}

struct Model {
    order0: Context,
    order1: HashMap<u8, Context>,
    order2: HashMap<u16, Context>,
}

impl Model {
    fn new() -> Self {
        Self {
            order0: Context::new(),
            order1: HashMap::new(),
            order2: HashMap::new(),
        }
    }

    fn encode_symbol(
        &self,
        symbol: u8,
        history: &[u8],
        encoder: &mut ArithmeticEncoder,
    ) -> io::Result<()> {
        if history.len() >= 2 {
            let key = order2_key(history);
            if let Some(context) = self.order2.get(&key) {
                if context.contains(symbol) {
                    return context.encode_symbol(symbol, encoder);
                }
                context.encode_escape(encoder)?;
            }
        }

        if !history.is_empty() {
            let key = history[0];
            if let Some(context) = self.order1.get(&key) {
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

    fn decode_symbol(&self, history: &[u8], decoder: &mut ArithmeticDecoder<'_>) -> io::Result<u8> {
        if history.len() >= 2 {
            let key = order2_key(history);
            if let Some(context) = self.order2.get(&key) {
                if let Some(symbol) = context.decode_symbol(decoder)? {
                    return Ok(symbol);
                }
            }
        }

        if !history.is_empty() {
            let key = history[0];
            if let Some(context) = self.order1.get(&key) {
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

    fn observe(&mut self, symbol: u8, history: &[u8]) {
        self.order0.observe(symbol);

        if !history.is_empty() {
            self.order1
                .entry(history[0])
                .or_insert_with(Context::new)
                .observe(symbol);
        }

        if history.len() >= 2 {
            self.order2
                .entry(order2_key(history))
                .or_insert_with(Context::new)
                .observe(symbol);
        }
    }
}

fn order2_key(history: &[u8]) -> u16 {
    ((history[1] as u16) << 8) | history[0] as u16
}

struct Context {
    counts: Box<[u16; SYMBOLS]>,
    total: u32,
    distinct: u16,
}

impl Context {
    fn new() -> Self {
        Self {
            counts: Box::new([0; SYMBOLS]),
            total: 0,
            distinct: 0,
        }
    }

    fn contains(&self, symbol: u8) -> bool {
        self.counts[symbol as usize] != 0
    }

    fn encode_symbol(&self, symbol: u8, encoder: &mut ArithmeticEncoder) -> io::Result<()> {
        let cum = self.cumulative(symbol);
        let freq = self.counts[symbol as usize] as u32;
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
        let slot = &mut self.counts[symbol as usize];
        if *slot == 0 {
            self.distinct = self.distinct.saturating_add(1);
        }

        *slot = slot.saturating_add(1);
        self.total = self.total.saturating_add(1);

        if self.total >= MAX_CONTEXT_TOTAL {
            self.rescale();
        }
    }

    fn cumulative(&self, symbol: u8) -> u32 {
        self.counts[..symbol as usize]
            .iter()
            .map(|&value| u32::from(value))
            .sum()
    }

    fn lookup(&self, target: u32) -> io::Result<(u8, u32, u32)> {
        let mut cum = 0u32;
        for (symbol, &freq) in self.counts.iter().enumerate() {
            let freq = u32::from(freq);
            if freq == 0 {
                continue;
            }

            if target < cum + freq {
                return Ok((symbol as u8, cum, freq));
            }
            cum += freq;
        }

        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "ppm symbol target out of range",
        ))
    }

    fn escape_freq(&self) -> u32 {
        u32::from(self.distinct.max(1))
    }

    fn total_with_escape(&self) -> u32 {
        self.total + self.escape_freq()
    }

    fn rescale(&mut self) {
        self.total = 0;
        self.distinct = 0;

        for count in self.counts.iter_mut() {
            if *count == 0 {
                continue;
            }

            *count = (*count).div_ceil(2).max(1);
            self.total += u32::from(*count);
            self.distinct += 1;
        }
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
    use super::{compress, decompress};

    #[test]
    fn roundtrip_repeated_text() {
        let input = b"banana bandana banana bandana banana bandana";
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
