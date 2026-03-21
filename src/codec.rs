use crate::{
    adaptive_huffman, block_huffman, byte_ppm, hybrid_ppm, lz77, ppmd, ppmd_bit, ppmd_mix, ppm,
    ppm_match_mix, wikimix,
};
use std::io::{self, Read, Write};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Codec {
    BlockHuffman,
    AdaptiveHuffman,
    Lz77,
    BytePpmO1,
    BytePpmO2,
    BytePpmO3,
    BytePpmO4,
    BytePpmO5,
    BytePpmO6,
    BitPpmO8,
    BitPpmO16,
    BitPpmO32,
    BitPpmO64,
    BytePpmMix,
    Ppmd,
    PpmdBit,
    PpmdMix,
    BitPpmMix,
    PpmMix,
    MatchModel,
    PpmMatchMix,
    WikiMix5,
}

impl Codec {
    pub fn name(self) -> &'static str {
        match self {
            Self::BlockHuffman => "huffman",
            Self::AdaptiveHuffman => "huffman-o1",
            Self::Lz77 => "lz77",
            Self::BytePpmO1 => "ppm-o1",
            Self::BytePpmO2 => "ppm-o2",
            Self::BytePpmO3 => "ppm",
            Self::BytePpmO4 => "ppm-o4",
            Self::BytePpmO5 => "ppm-o5",
            Self::BytePpmO6 => "ppm-o6",
            Self::BitPpmO8 => "ppm-bit",
            Self::BitPpmO16 => "ppm-bit-o16",
            Self::BitPpmO32 => "ppm-bit-o32",
            Self::BitPpmO64 => "ppm-bit-o64",
            Self::BytePpmMix => "ppm-byte-mix",
            Self::Ppmd => "ppmd",
            Self::PpmdBit => "ppmd-bit",
            Self::PpmdMix => "ppmd-mix",
            Self::BitPpmMix => "ppm-bit-mix",
            Self::PpmMix => "ppm-mix",
            Self::MatchModel => "match",
            Self::PpmMatchMix => "ppm-match-mix",
            Self::WikiMix5 => "wikimix5",
        }
    }

    pub fn parse(value: &str) -> io::Result<Self> {
        match value {
            "block-huffman" | "huffman" => Ok(Self::BlockHuffman),
            "adaptive-huffman" | "context-huffman" | "huffman-o1" => Ok(Self::AdaptiveHuffman),
            "lz77" => Ok(Self::Lz77),
            "ppm-o1" | "ppm1" => Ok(Self::BytePpmO1),
            "ppm-o2" | "ppm2" => Ok(Self::BytePpmO2),
            "ppm" | "ppm-o3" | "ppm3" => Ok(Self::BytePpmO3),
            "ppm-o4" | "ppm4" => Ok(Self::BytePpmO4),
            "ppm-o5" | "ppm5" => Ok(Self::BytePpmO5),
            "ppm-o6" | "ppm6" => Ok(Self::BytePpmO6),
            "ppm-bit" | "ppm-bit-o8" => Ok(Self::BitPpmO8),
            "ppm-bit-o16" => Ok(Self::BitPpmO16),
            "ppm-bit-o32" => Ok(Self::BitPpmO32),
            "ppm-bit-o64" => Ok(Self::BitPpmO64),
            "ppm-byte-mix" | "ppm-mix-byte" | "ppmbmix" => Ok(Self::BytePpmMix),
            "ppmd" => Ok(Self::Ppmd),
            "ppmd-bit" | "ppmdbit" => Ok(Self::PpmdBit),
            "ppmd-mix" | "ppmdmix" => Ok(Self::PpmdMix),
            "ppm-bit-mix" | "ppmbitmix" => Ok(Self::BitPpmMix),
            "ppm-mix" | "ppmmix" | "pmix" => Ok(Self::PpmMix),
            "match" | "match-model" | "match-only" => Ok(Self::MatchModel),
            "ppm-match-mix" | "ppmmatchmix" | "pmmatch" => Ok(Self::PpmMatchMix),
            "wikimix5" | "wikimix" | "wmx5" => Ok(Self::WikiMix5),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("unknown codec: {value}"),
            )),
        }
    }

    pub fn compress<R: Read, W: Write>(self, input: R, output: W) -> io::Result<()> {
        match self {
            Self::BlockHuffman => block_huffman::compress(input, output),
            Self::AdaptiveHuffman => adaptive_huffman::compress(input, output),
            Self::Lz77 => lz77::compress(input, output),
            Self::BytePpmO1 => byte_ppm::compress_order1(input, output),
            Self::BytePpmO2 => byte_ppm::compress_order2(input, output),
            Self::BytePpmO3 => byte_ppm::compress_order3(input, output),
            Self::BytePpmO4 => byte_ppm::compress_order4(input, output),
            Self::BytePpmO5 => byte_ppm::compress_order5(input, output),
            Self::BytePpmO6 => byte_ppm::compress_order6(input, output),
            Self::BitPpmO8 => ppm::compress_order8(input, output),
            Self::BitPpmO16 => ppm::compress_order16(input, output),
            Self::BitPpmO32 => ppm::compress_order32(input, output),
            Self::BitPpmO64 => ppm::compress_order64(input, output),
            Self::BytePpmMix => byte_ppm::compress_mix(input, output),
            Self::Ppmd => ppmd::compress(input, output),
            Self::PpmdBit => ppmd_bit::compress(input, output),
            Self::PpmdMix => ppmd_mix::compress(input, output),
            Self::BitPpmMix => ppm::compress_mix(input, output),
            Self::PpmMix => hybrid_ppm::compress(input, output),
            Self::MatchModel => ppm_match_mix::compress_match_only(input, output),
            Self::PpmMatchMix => ppm_match_mix::compress(input, output),
            Self::WikiMix5 => wikimix::compress(input, output),
        }
    }
}

pub fn decompress_auto<W: Write>(input: &[u8], output: W) -> io::Result<()> {
    if input.len() < 4 {
        return Err(io::Error::new(
            io::ErrorKind::UnexpectedEof,
            "archive too small to detect codec",
        ));
    }

    if &input[..4] == block_huffman::magic() {
        block_huffman::decompress(input, output)
    } else if &input[..4] == adaptive_huffman::magic() {
        adaptive_huffman::decompress(input, output)
    } else if &input[..4] == lz77::magic() {
        lz77::decompress(input, output)
    } else if &input[..4] == byte_ppm::magic_order1() {
        byte_ppm::decompress_order1(input, output)
    } else if &input[..4] == byte_ppm::magic_order2() {
        byte_ppm::decompress_order2(input, output)
    } else if &input[..4] == byte_ppm::magic_order3() {
        byte_ppm::decompress_order3(input, output)
    } else if &input[..4] == byte_ppm::magic_order4() {
        byte_ppm::decompress_order4(input, output)
    } else if &input[..4] == byte_ppm::magic_order5() {
        byte_ppm::decompress_order5(input, output)
    } else if &input[..4] == byte_ppm::magic_order6() {
        byte_ppm::decompress_order6(input, output)
    } else if &input[..4] == ppm::magic_order8() {
        ppm::decompress_order8(input, output)
    } else if &input[..4] == ppm::magic_order16() {
        ppm::decompress_order16(input, output)
    } else if &input[..4] == ppm::magic_order32() {
        ppm::decompress_order32(input, output)
    } else if &input[..4] == ppm::magic_order64() {
        ppm::decompress_order64(input, output)
    } else if &input[..4] == byte_ppm::magic_mix() {
        byte_ppm::decompress_mix(input, output)
    } else if &input[..4] == ppmd::magic() {
        ppmd::decompress(input, output)
    } else if &input[..4] == ppmd_bit::magic() {
        ppmd_bit::decompress(input, output)
    } else if &input[..4] == ppmd_mix::magic() {
        ppmd_mix::decompress(input, output)
    } else if &input[..4] == ppm::magic_mix() {
        ppm::decompress_mix(input, output)
    } else if &input[..4] == hybrid_ppm::magic() {
        hybrid_ppm::decompress(input, output)
    } else if &input[..4] == ppm_match_mix::magic_match_only() {
        ppm_match_mix::decompress_match_only(input, output)
    } else if &input[..4] == ppm_match_mix::magic_legacy() {
        ppm_match_mix::decompress(input, output)
    } else if &input[..4] == ppm_match_mix::magic() {
        ppm_match_mix::decompress(input, output)
    } else if &input[..4] == wikimix::magic() {
        wikimix::decompress(input, output)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unknown archive format",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::Codec;

    #[test]
    fn ppm_names_select_distinct_byte_and_bit_families() {
        assert_eq!(Codec::parse("ppm-o6").unwrap(), Codec::BytePpmO6);
        assert_eq!(Codec::parse("ppm-bit-o64").unwrap(), Codec::BitPpmO64);
        assert_eq!(Codec::parse("ppm").unwrap(), Codec::BytePpmO3);
        assert_eq!(Codec::parse("ppm-bit").unwrap(), Codec::BitPpmO8);
        assert_eq!(Codec::parse("ppm-byte-mix").unwrap(), Codec::BytePpmMix);
        assert_eq!(Codec::parse("ppmd").unwrap(), Codec::Ppmd);
        assert_eq!(Codec::parse("ppmd-bit").unwrap(), Codec::PpmdBit);
        assert_eq!(Codec::parse("ppmd-mix").unwrap(), Codec::PpmdMix);
        assert_eq!(Codec::parse("ppm-bit-mix").unwrap(), Codec::BitPpmMix);
        assert_eq!(Codec::parse("ppm-mix").unwrap(), Codec::PpmMix);
        assert_eq!(Codec::parse("match").unwrap(), Codec::MatchModel);
        assert_eq!(Codec::parse("ppm-match-mix").unwrap(), Codec::PpmMatchMix);
    }
}
