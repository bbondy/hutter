use crate::{adaptive_huffman, block_huffman, byte_ppm, lz77, ppm, wikimix};
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
    BitPpmO1,
    BitPpmO2,
    BitPpmO3,
    BitPpmO4,
    BitPpmO5,
    BitPpmO6,
    PpmMix,
    WikiMix5,
}

impl Codec {
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
            "ppm-bit-o1" => Ok(Self::BitPpmO1),
            "ppm-bit-o2" => Ok(Self::BitPpmO2),
            "ppm-bit" | "ppm-bit-o3" => Ok(Self::BitPpmO3),
            "ppm-bit-o4" => Ok(Self::BitPpmO4),
            "ppm-bit-o5" => Ok(Self::BitPpmO5),
            "ppm-bit-o6" => Ok(Self::BitPpmO6),
            "ppm-bit-mix" | "ppm-mix" | "ppmmix" | "pmix" => Ok(Self::PpmMix),
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
            Self::BitPpmO1 => ppm::compress_order1(input, output),
            Self::BitPpmO2 => ppm::compress_order2(input, output),
            Self::BitPpmO3 => ppm::compress_order3(input, output),
            Self::BitPpmO4 => ppm::compress_order4(input, output),
            Self::BitPpmO5 => ppm::compress_order5(input, output),
            Self::BitPpmO6 => ppm::compress_order6(input, output),
            Self::PpmMix => ppm::compress_mix(input, output),
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
    } else if &input[..4] == ppm::magic_order1() {
        ppm::decompress_order1(input, output)
    } else if &input[..4] == ppm::magic_order2() {
        ppm::decompress_order2(input, output)
    } else if &input[..4] == ppm::magic_order3() {
        ppm::decompress_order3(input, output)
    } else if &input[..4] == ppm::magic_order4() {
        ppm::decompress_order4(input, output)
    } else if &input[..4] == ppm::magic_order5() {
        ppm::decompress_order5(input, output)
    } else if &input[..4] == ppm::magic_order6() {
        ppm::decompress_order6(input, output)
    } else if &input[..4] == ppm::magic_mix() {
        ppm::decompress_mix(input, output)
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
        assert_eq!(Codec::parse("ppm-bit-o6").unwrap(), Codec::BitPpmO6);
        assert_eq!(Codec::parse("ppm").unwrap(), Codec::BytePpmO3);
        assert_eq!(Codec::parse("ppm-bit").unwrap(), Codec::BitPpmO3);
    }
}
