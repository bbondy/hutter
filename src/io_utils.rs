use crate::progress::Progress;
use std::fs::File;
use std::io::{self, Read};
use std::path::Path;

pub fn read_file_with_progress(path: &str, label: &str) -> io::Result<Vec<u8>> {
    let file = File::open(path)?;
    let total = file.metadata()?.len();
    let progress = Progress::new(label, total);
    let mut reader = progress.reader(file);
    let mut data = Vec::new();
    reader.read_to_end(&mut data)?;
    progress.finish(&format!("{label} done"));
    Ok(data)
}

pub fn file_len(path: &str) -> io::Result<u64> {
    Ok(File::open(Path::new(path))?.metadata()?.len())
}
