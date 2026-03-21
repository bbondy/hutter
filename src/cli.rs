use crate::codec::Codec;
use std::io;

pub enum Command<'a> {
    Compress {
        codec: Codec,
        input_path: &'a str,
        output_path: &'a str,
        show_progress: bool,
    },
    Decompress {
        input_path: &'a str,
        output_path: &'a str,
        show_progress: bool,
    },
    Stats {
        input_path: &'a str,
        archive_path: &'a str,
        show_progress: bool,
    },
    Profile {
        input_path: &'a str,
        show_progress: bool,
    },
}

pub fn parse_args<'a>(args: &'a [String]) -> io::Result<Command<'a>> {
    if args.len() < 2 {
        return Err(usage_error("missing command"));
    }

    let show_progress = !args.iter().any(|arg| arg == "--no-progress");

    match args[1].as_str() {
        "compress" => parse_compress_args(args, show_progress),
        "decompress" => parse_decompress_args(args, show_progress),
        "stats" => parse_stats_args(args, show_progress),
        "profile" => parse_profile_args(args, show_progress),
        _ => Err(usage_error("unknown command")),
    }
}

pub fn print_usage(program: &str) {
    eprintln!("usage:");
    eprintln!(
        "  {program} compress [--no-progress] [--codec huffman|huffman-o1|lz77|ppm-o1|ppm-o2|ppm|ppm-o4|ppm-o5|ppm-o6|ppm-byte-mix|ppmd|ppmd-bit|ppm-bit|ppm-bit-o16|ppm-bit-o32|ppm-bit-o64|ppm-bit-mix|ppm-mix|match|ppm-match-mix|wikimix5] <input> <archive>"
    );
    eprintln!(
        "  note: ppm-oN is byte-level PPM; ppmd is byte-level exclusion-based PPMD-style; ppmd-bit and ppm-bit-oN are bit-level coders; match is the standalone LZ-style match predictor"
    );
    eprintln!("  {program} decompress [--no-progress] <archive> <output>");
    eprintln!("  {program} stats [--no-progress] <input> <archive>");
    eprintln!("  {program} profile [--no-progress] <input>");
    eprintln!("  note: profile benchmarks internal ppm-match-mix model combinations");
}

fn parse_compress_args<'a>(args: &'a [String], show_progress: bool) -> io::Result<Command<'a>> {
    let filtered = filtered_args(args);
    match filtered.as_slice() {
        [_, _, input_path, output_path] => Ok(Command::Compress {
            codec: Codec::BlockHuffman,
            input_path,
            output_path,
            show_progress,
        }),
        [_, _, flag, codec, input_path, output_path] if *flag == "--codec" => {
            Ok(Command::Compress {
                codec: Codec::parse(codec)?,
                input_path,
                output_path,
                show_progress,
            })
        }
        _ => Err(usage_error("invalid compress arguments")),
    }
}

fn parse_decompress_args<'a>(args: &'a [String], show_progress: bool) -> io::Result<Command<'a>> {
    let filtered = filtered_args(args);
    match filtered.as_slice() {
        [_, _, input_path, output_path] => Ok(Command::Decompress {
            input_path,
            output_path,
            show_progress,
        }),
        _ => Err(usage_error("invalid arguments")),
    }
}

fn parse_stats_args<'a>(args: &'a [String], show_progress: bool) -> io::Result<Command<'a>> {
    let filtered = filtered_args(args);
    match filtered.as_slice() {
        [_, _, input_path, archive_path] => Ok(Command::Stats {
            input_path,
            archive_path,
            show_progress,
        }),
        _ => Err(usage_error("invalid arguments")),
    }
}

fn parse_profile_args<'a>(args: &'a [String], show_progress: bool) -> io::Result<Command<'a>> {
    let filtered = filtered_args(args);
    match filtered.as_slice() {
        [_, _, input_path] => Ok(Command::Profile {
            input_path,
            show_progress,
        }),
        _ => Err(usage_error("invalid arguments")),
    }
}

fn filtered_args<'a>(args: &'a [String]) -> Vec<&'a str> {
    args.iter()
        .map(String::as_str)
        .filter(|arg| *arg != "--no-progress")
        .collect()
}

fn usage_error(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message)
}
