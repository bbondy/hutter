use std::fmt::Write as _;
use std::io::{self, Read, Write};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU8, AtomicU64, Ordering};
use std::thread;
use std::time::{Duration, Instant};

const PHASE_READING: u8 = 0;
const PHASE_PROCESSING: u8 = 1;

pub struct Progress {
    state: Arc<State>,
    worker: Option<thread::JoinHandle<()>>,
    enabled: bool,
}

struct State {
    label: String,
    total: u64,
    bytes: AtomicU64,
    phase: AtomicU8,
    finished: AtomicBool,
}

impl Progress {
    pub fn with_enabled(label: impl Into<String>, total: u64, enabled: bool) -> Self {
        let state = Arc::new(State {
            label: label.into(),
            total,
            bytes: AtomicU64::new(0),
            phase: AtomicU8::new(PHASE_READING),
            finished: AtomicBool::new(false),
        });

        let worker = if enabled {
            let state = Arc::clone(&state);
            Some(thread::spawn(move || render_loop(state)))
        } else {
            None
        };

        Self {
            state,
            worker,
            enabled,
        }
    }

    pub fn reader<R: Read>(&self, inner: R) -> ProgressReader<R> {
        ProgressReader {
            inner,
            state: Arc::clone(&self.state),
        }
    }

    pub fn set_processing(&self) {
        self.state.phase.store(PHASE_PROCESSING, Ordering::Relaxed);
    }

    pub fn finish(mut self, message: &str) {
        self.state.finished.store(true, Ordering::Relaxed);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }

        if self.enabled {
            let _ = writeln!(io::stderr(), "\r{message}\x1b[K");
        }
    }
}

pub struct ProgressReader<R> {
    inner: R,
    state: Arc<State>,
}

impl<R: Read> Read for ProgressReader<R> {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        let read = self.inner.read(buf)?;
        if read == 0 {
            self.state.phase.store(PHASE_PROCESSING, Ordering::Relaxed);
        } else {
            self.state.bytes.fetch_add(read as u64, Ordering::Relaxed);
        }
        Ok(read)
    }
}

fn render_loop(state: Arc<State>) {
    let frames = [
        "[>   ]", "[=>  ]", "[==> ]", "[===>]", "[ ==>]", "[  =>]", "[   >]",
    ];
    let start = Instant::now();
    let mut frame = 0usize;

    while !state.finished.load(Ordering::Relaxed) {
        let line = if state.phase.load(Ordering::Relaxed) == PHASE_READING && state.total > 0 {
            render_bar(
                &state.label,
                state.bytes.load(Ordering::Relaxed),
                state.total,
                start.elapsed(),
            )
        } else {
            format!(
                "{} {} {:>6.1}s",
                frames[frame % frames.len()],
                state.label,
                start.elapsed().as_secs_f64()
            )
        };

        let _ = write!(io::stderr(), "\r{line}\x1b[K");
        let _ = io::stderr().flush();
        frame += 1;
        thread::sleep(Duration::from_millis(100));
    }
}

fn render_bar(label: &str, current: u64, total: u64, elapsed: Duration) -> String {
    let width = 24usize;
    let ratio = if total == 0 {
        1.0
    } else {
        (current as f64 / total as f64).clamp(0.0, 1.0)
    };
    let filled = (ratio * width as f64).round() as usize;

    let mut bar = String::with_capacity(width + 2);
    bar.push('[');
    for idx in 0..width {
        if idx < filled {
            bar.push('=');
        } else {
            bar.push(' ');
        }
    }
    bar.push(']');

    let mut line = String::new();
    let _ = write!(
        &mut line,
        "{} {} {:>3.0}% {}/{} {:>6.1}s",
        bar,
        label,
        ratio * 100.0,
        human_bytes(current),
        human_bytes(total),
        elapsed.as_secs_f64()
    );
    line
}

fn human_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KB", "MB", "GB", "TB"];
    let mut value = bytes as f64;
    let mut unit = 0usize;
    while value >= 1024.0 && unit + 1 < UNITS.len() {
        value /= 1024.0;
        unit += 1;
    }

    if unit == 0 {
        format!("{bytes}{}", UNITS[unit])
    } else {
        format!("{value:.1}{}", UNITS[unit])
    }
}
