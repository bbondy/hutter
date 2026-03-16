mod adaptive_huffman;

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
    if args.len() < 2 {
        print_usage(&args[0]);
        process::exit(2);
    }

    match args[1].as_str() {
        "compress" => {
            if args.len() != 4 {
                print_usage(&args[0]);
                process::exit(2);
            }
            let input = fs::File::open(&args[2])?;
            let output = fs::File::create(&args[3])?;
            adaptive_huffman::compress(input, output)
        }
        "decompress" => {
            if args.len() != 4 {
                print_usage(&args[0]);
                process::exit(2);
            }
            let input = fs::File::open(&args[2])?;
            let output = fs::File::create(&args[3])?;
            adaptive_huffman::decompress(input, output)
        }
        "stats" => {
            if args.len() != 4 {
                print_usage(&args[0]);
                process::exit(2);
            }
            print_stats(&args[2], &args[3])
        }
        _ => {
            print_usage(&args[0]);
            process::exit(2);
        }
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

fn print_usage(program: &str) {
    eprintln!("usage:");
    eprintln!("  {program} compress <input> <archive>");
    eprintln!("  {program} decompress <archive> <output>");
    eprintln!("  {program} stats <input> <archive>");
}
