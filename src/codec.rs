use crate::{adaptive_huffman, block_huffman, lz77, ppm};
use std::io::{self, Read, Write};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Codec {
    BlockHuffman,
    AdaptiveHuffman,
    Lz77,
    PpmO1,
    PpmO2,
    PpmO3,
}

impl Codec {
    pub fn parse(value: &str) -> io::Result<Self> {
        match value {
            "block-huffman" | "huffman" => Ok(Self::BlockHuffman),
            "adaptive-huffman" | "context-huffman" | "huffman-o1" => Ok(Self::AdaptiveHuffman),
            "lz77" => Ok(Self::Lz77),
            "ppm-o1" | "ppm1" => Ok(Self::PpmO1),
            "ppm-o2" | "ppm2" => Ok(Self::PpmO2),
            "ppm" | "ppm-o3" | "ppm3" => Ok(Self::PpmO3),
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
            Self::PpmO1 => ppm::compress_order1(input, output),
            Self::PpmO2 => ppm::compress_order2(input, output),
            Self::PpmO3 => ppm::compress_order3(input, output),
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
    } else if &input[..4] == ppm::magic_order1() {
        ppm::decompress_order1(input, output)
    } else if &input[..4] == ppm::magic_order2() {
        ppm::decompress_order2(input, output)
    } else if &input[..4] == ppm::magic_order3() {
        ppm::decompress_order3(input, output)
    } else if input[..4] == *b"PPM0" {
        ppm::decompress_legacy_order3(input, output)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unknown archive format",
        ))
    }
}
