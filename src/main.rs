mod adaptive_huffman;
mod block_huffman;
mod byte_ppm;
mod cli;
mod codec;
mod hybrid_ppm;
mod io_utils;
mod lz77;
mod ppmd;
mod ppmd_bit;
mod ppm;
mod ppm_match_mix;
mod progress;
mod wikimix;

use crate::cli::Command;
use crate::codec::decompress_auto;
use crate::io_utils::{file_len, read_file_with_progress};
use crate::progress::Progress;
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
            show_progress,
        } => {
            let input = fs::File::open(input_path)?;
            let input_size = input.metadata()?.len();
            let output = fs::File::create(output_path)?;
            let progress = Progress::with_enabled(
                format!("compressing {}", codec.name()),
                input_size,
                show_progress,
            );
            let tracked_input = progress.reader(input);
            let result = codec.compress(tracked_input, output);
            progress.finish(&format!("compressing {} done", codec.name()));
            result
        }
        Command::Decompress {
            input_path,
            output_path,
            show_progress,
        } => {
            let input = read_file_with_progress(input_path, "reading archive", show_progress)?;
            let output = fs::File::create(output_path)?;
            let input_size = input.len() as u64;
            let progress =
                Progress::with_enabled("decompressing archive", input_size, show_progress);
            progress.set_processing();
            let result = decompress_auto(&input, output);
            progress.finish("decompressing archive done");
            result
        }
        Command::Stats {
            input_path,
            archive_path,
            show_progress,
        } => print_stats(input_path, archive_path, show_progress),
        Command::Profile {
            input_path,
            show_progress,
        } => print_profile(input_path, show_progress),
    }
}

fn print_stats(input_path: &str, archive_path: &str, show_progress: bool) -> io::Result<()> {
    let progress = Progress::with_enabled("collecting stats", 0, show_progress);
    progress.set_processing();
    let input_size = file_len(input_path)?;
    let archive_size = file_len(archive_path)?;
    let exe_size = current_exe_size()?;
    progress.finish("collecting stats done");
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

fn print_profile(input_path: &str, show_progress: bool) -> io::Result<()> {
    let input = read_file_with_progress(input_path, "reading profile input", show_progress)?;
    let progress = Progress::with_enabled("profiling ppm-match-mix", 0, show_progress);
    progress.set_processing();
    let results = ppm_match_mix::profile_model_configs(&input[..])?;
    progress.finish("profiling ppm-match-mix done");

    println!("input: {} bytes", input.len());
    println!(
        "{:<16} {:>12} {:>14} {:>14}",
        "config", "time_ms", "ns/byte", "archive_bytes"
    );
    for result in &results {
        println!(
            "{:<16} {:>12.3} {:>14.1} {:>14}",
            result.name,
            result.elapsed.as_secs_f64() * 1000.0,
            result.ns_per_byte,
            result.output_size
        );
    }

    if let Some(full) = results.iter().find(|result| result.name == "ppm-match-mix") {
        for result in &results {
            if result.name == full.name {
                continue;
            }

            let saved = if full.elapsed.is_zero() {
                0.0
            } else {
                (full.elapsed.as_secs_f64() - result.elapsed.as_secs_f64())
                    / full.elapsed.as_secs_f64()
                    * 100.0
            };
            println!(
                "save vs full by dropping to {:<16}: {:>6.2}%",
                result.name, saved
            );
        }
    }

    Ok(())
}

fn current_exe_size() -> io::Result<u64> {
    let exe = env::current_exe()?;
    Ok(fs::metadata(Path::new(&exe))?.len())
}
