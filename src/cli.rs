use crate::codec::Codec;
use std::io;

pub enum Command<'a> {
    Compress {
        codec: Codec,
        input_path: &'a str,
        output_path: &'a str,
    },
    Decompress {
        input_path: &'a str,
        output_path: &'a str,
    },
    Stats {
        input_path: &'a str,
        archive_path: &'a str,
    },
}

pub fn parse_args<'a>(args: &'a [String]) -> io::Result<Command<'a>> {
    if args.len() < 2 {
        return Err(usage_error("missing command"));
    }

    match args[1].as_str() {
        "compress" => parse_compress_args(args),
        "decompress" if args.len() == 4 => Ok(Command::Decompress {
            input_path: &args[2],
            output_path: &args[3],
        }),
        "stats" if args.len() == 4 => Ok(Command::Stats {
            input_path: &args[2],
            archive_path: &args[3],
        }),
        "decompress" | "stats" => Err(usage_error("invalid arguments")),
        _ => Err(usage_error("unknown command")),
    }
}

pub fn print_usage(program: &str) {
    eprintln!("usage:");
    eprintln!("  {program} compress [--codec huffman|huffman-o1|lz77|ppm] <input> <archive>");
    eprintln!("  {program} decompress <archive> <output>");
    eprintln!("  {program} stats <input> <archive>");
}

fn parse_compress_args<'a>(args: &'a [String]) -> io::Result<Command<'a>> {
    match args.len() {
        4 => Ok(Command::Compress {
            codec: Codec::BlockHuffman,
            input_path: &args[2],
            output_path: &args[3],
        }),
        6 if args[2] == "--codec" => Ok(Command::Compress {
            codec: Codec::parse(&args[3])?,
            input_path: &args[4],
            output_path: &args[5],
        }),
        _ => Err(usage_error("invalid compress arguments")),
    }
}

fn usage_error(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message)
}
