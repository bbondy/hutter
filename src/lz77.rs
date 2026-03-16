use std::io::{self, Read, Write};

const MAGIC: &[u8; 4] = b"LZ77";
const WINDOW_SIZE: usize = 4 * 1024;
const MIN_MATCH: usize = 3;
const MAX_MATCH: usize = u8::MAX as usize;

pub fn magic() -> &'static [u8; 4] {
    MAGIC
}

pub fn compress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut data = Vec::new();
    input.read_to_end(&mut data)?;

    output.write_all(MAGIC)?;
    output.write_all(&(data.len() as u64).to_le_bytes())?;

    let mut index = 0usize;
    while index < data.len() {
        let (distance, length) = find_match(&data, index);
        if length >= MIN_MATCH {
            output.write_all(&[1])?;
            output.write_all(&(distance as u16).to_le_bytes())?;
            output.write_all(&[length as u8])?;
            index += length;
        } else {
            output.write_all(&[0, data[index]])?;
            index += 1;
        }
    }

    Ok(())
}

pub fn decompress<R: Read, W: Write>(mut input: R, mut output: W) -> io::Result<()> {
    let mut magic = [0u8; 4];
    input.read_exact(&mut magic)?;
    if &magic != MAGIC {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid archive magic",
        ));
    }

    let original_size = read_u64(&mut input)? as usize;
    let mut restored = Vec::with_capacity(original_size);

    while restored.len() < original_size {
        let mut tag = [0u8; 1];
        input.read_exact(&mut tag)?;

        match tag[0] {
            0 => {
                let mut byte = [0u8; 1];
                input.read_exact(&mut byte)?;
                restored.push(byte[0]);
            }
            1 => {
                let distance = read_u16(&mut input)? as usize;
                let mut len = [0u8; 1];
                input.read_exact(&mut len)?;
                let length = len[0] as usize;

                if distance == 0 || distance > restored.len() || length < MIN_MATCH {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "invalid lz77 back-reference",
                    ));
                }

                let start = restored.len() - distance;
                for offset in 0..length {
                    let byte = restored[start + offset % distance];
                    restored.push(byte);
                }
            }
            _ => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid lz77 token tag",
                ));
            }
        }

        if restored.len() > original_size {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "decoded past expected output size",
            ));
        }
    }

    output.write_all(&restored)?;
    Ok(())
}

fn find_match(data: &[u8], index: usize) -> (usize, usize) {
    if index + MIN_MATCH > data.len() {
        return (0, 0);
    }

    let window_start = index.saturating_sub(WINDOW_SIZE);
    let mut best_distance = 0usize;
    let mut best_length = 0usize;

    for candidate in window_start..index {
        let mut length = 0usize;
        while length < MAX_MATCH
            && index + length < data.len()
            && data[candidate + (length % (index - candidate).max(1))] == data[index + length]
        {
            length += 1;
        }

        if length > best_length {
            best_length = length;
            best_distance = index - candidate;
            if best_length == MAX_MATCH {
                break;
            }
        }
    }

    (best_distance, best_length)
}

fn read_u16<R: Read>(input: &mut R) -> io::Result<u16> {
    let mut buf = [0u8; 2];
    input.read_exact(&mut buf)?;
    Ok(u16::from_le_bytes(buf))
}

fn read_u64<R: Read>(input: &mut R) -> io::Result<u64> {
    let mut buf = [0u8; 8];
    input.read_exact(&mut buf)?;
    Ok(u64::from_le_bytes(buf))
}

#[cfg(test)]
mod tests {
    use super::{compress, decompress};

    #[test]
    fn roundtrip_repeated_text() {
        let input = b"banana bandana banana bandana banana bandana";
        let mut compressed = Vec::new();
        compress(&input[..], &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }

    #[test]
    fn roundtrip_binary() {
        let input: Vec<u8> = (0..=255).cycle().take(2048).collect();
        let mut compressed = Vec::new();
        compress(&input[..], &mut compressed).unwrap();

        let mut restored = Vec::new();
        decompress(&compressed[..], &mut restored).unwrap();
        assert_eq!(restored, input);
    }
}
