use crate::{adaptive_huffman, lz77};
use std::io::{self, Read, Write};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Codec {
    AdaptiveHuffman,
    Lz77,
}

impl Codec {
    pub fn parse(value: &str) -> io::Result<Self> {
        match value {
            "adaptive-huffman" | "huffman" => Ok(Self::AdaptiveHuffman),
            "lz77" => Ok(Self::Lz77),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("unknown codec: {value}"),
            )),
        }
    }

    pub fn compress<R: Read, W: Write>(self, input: R, output: W) -> io::Result<()> {
        match self {
            Self::AdaptiveHuffman => adaptive_huffman::compress(input, output),
            Self::Lz77 => lz77::compress(input, output),
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

    if &input[..4] == adaptive_huffman::magic() {
        adaptive_huffman::decompress(input, output)
    } else if &input[..4] == lz77::magic() {
        lz77::decompress(input, output)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unknown archive format",
        ))
    }
}
