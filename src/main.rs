mod adaptive_huffman;
mod block_huffman;
mod cli;
mod codec;
mod lz77;
mod ppm;
mod wikimix;

use crate::cli::Command;
use crate::codec::decompress_auto;
use std::env;
use std::fs;
use std::io;
use std::path::Path;
use std::process;

fn main() {
    if let Err(err) = run() {
        eprintln!("error: {err}");
        process::exit(1);
    }
}

fn run() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    let command = match cli::parse_args(&args) {
        Ok(command) => command,
        Err(_) => {
            cli::print_usage(&args[0]);
            process::exit(2);
        }
    };

    match command {
        Command::Compress {
            codec,
            input_path,
            output_path,
        } => {
            let input = fs::File::open(input_path)?;
            let output = fs::File::create(output_path)?;
            codec.compress(input, output)
        }
        Command::Decompress {
            input_path,
            output_path,
        } => {
            let input = fs::read(input_path)?;
            let output = fs::File::create(output_path)?;
            decompress_auto(&input, output)
        }
        Command::Stats {
            input_path,
            archive_path,
        } => print_stats(input_path, archive_path),
    }
}

fn print_stats(input_path: &str, archive_path: &str) -> io::Result<()> {
    let input_size = fs::metadata(input_path)?.len();
    let archive_size = fs::metadata(archive_path)?.len();
    let exe_size = current_exe_size()?;
    let total_size = archive_size + exe_size;
    let ratio = if archive_size == 0 {
        0.0
    } else {
        input_size as f64 / archive_size as f64
    };

    println!("input:        {} bytes", input_size);
    println!("archive:      {} bytes", archive_size);
    println!("compressor:   {} bytes", exe_size);
    println!("total S:      {} bytes", total_size);
    println!("archive ratio {:.4}x", ratio);
    println!("note: Hutter Prize compares total S, not archive size alone");

    Ok(())
}

fn current_exe_size() -> io::Result<u64> {
    let exe = env::current_exe()?;
    Ok(fs::metadata(Path::new(&exe))?.len())
}
