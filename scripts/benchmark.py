#!/usr/bin/env python3
"""Serial round-trip benchmarks on macOS/Linux, with JSONL results and per-phase RSS.

Build first with cargo build --release. Sizes here are development measurements,
not submission scores. Each phase has a timeout; no hard memory cap is imposed.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import time

from make_samples import digest

CODECS = ("huffman huffman-o1 lz77 ppm-o1 ppm-o2 ppm ppm-o4 ppm-o5 ppm-o6 "
          "ppm-byte-mix ppmd ppmd-bit ppmd-mix ppm-bit ppm-bit-o16 ppm-bit-o32 "
          "ppm-bit-o64 ppm-bit-mix ppm-mix match ppm-match-mix wikimix5").split()


def capture(*command):
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, errors="replace", timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def measured(command, log, timeout, output=None):
    darwin = platform.system() == "Darwin"
    timer = ["/usr/bin/time", "-l"] if darwin else ["/usr/bin/time", "-v"]
    start = time.perf_counter()
    with log.open("wb") as stderr, (output.open("wb") if output else open(os.devnull, "wb")) as stdout:
        process = subprocess.Popen(timer + command, stdout=stdout, stderr=stderr,
                                   start_new_session=True, env={**os.environ, "LC_ALL": "C"})
        try:
            code = process.wait(timeout=timeout)
            status = "ok" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            code, status = None, "timeout"
    elapsed = time.perf_counter() - start
    report = log.read_text(errors="replace")
    pattern = r"(\d+)\s+maximum resident set size" if darwin else r"Maximum resident set size \(kbytes\):\s*(\d+)"
    match = re.search(pattern, report)
    rss = int(match[1]) * (1 if darwin else 1024) if match else None
    return {"command": command, "status": status, "exit_code": code,
            "wall_seconds": elapsed, "peak_rss_bytes": rss, "log": str(log)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--codecs", nargs="+", default=CODECS,
                        choices=CODECS + ["gzip", "bzip2", "xz"])
    parser.add_argument("--binary", type=Path, default=Path("target/release/hutter-starter"))
    parser.add_argument("--output", type=Path, required=True, help="new directory; refuses overwrite")
    parser.add_argument("--timeout", type=float, default=120, help="seconds per compress/decompress phase")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--record", help="also save a compact, Git-trackable history under this unique ID")
    parser.add_argument("--note", default="", help="hypothesis or conclusion for the history record")
    parser.add_argument("--manifest", type=Path, help="sample manifest to retain with the history")
    args = parser.parse_args()
    if args.timeout <= 0 or args.repeats < 1:
        parser.error("timeout and repeats must be positive")
    if args.record:
        from benchmark_history import ROOT
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.record) or not args.note:
            parser.error("--record needs a simple unique ID and a nonempty --note")
        if (ROOT / args.record).exists():
            parser.error("history ID already exists; choose a new ID")
    source_binary = args.binary.resolve()
    if not source_binary.is_file() or not all(p.is_file() for p in args.inputs):
        parser.error("build the release binary first and provide existing input files")
    args.output.mkdir(parents=True, exist_ok=False)
    # Freeze the executable so a concurrent rebuild cannot change later trials.
    binary = (args.output / "hutter-starter").resolve()
    shutil.copy2(source_binary, binary)
    metadata = {"schema_version": 1, "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "commit": capture("git", "rev-parse", "HEAD"),
                "git_status": capture("git", "status", "--porcelain"),
                "platform": platform.platform(), "machine": platform.machine(),
                "cpu": capture("sysctl", "-n", "machdep.cpu.brand_string") if platform.system() == "Darwin" else platform.processor(),
                "rustc": capture("rustc", "-Vv"), "binary": str(binary),
                "source_binary": str(source_binary), "runner_sha256": digest(Path(__file__)),
                "source_sha256": {str(path): digest(path) for path in sorted(Path("src").rglob("*.rs"))},
                "binary_bytes": binary.stat().st_size, "binary_sha256": digest(binary),
                "rustflags": os.environ.get("RUSTFLAGS", ""),
                "timeout_seconds": args.timeout, "repeats": args.repeats,
                "external_binary_sha256": {name: digest(Path(shutil.which(name)))
                                           for name in args.codecs if name in ("gzip", "bzip2", "xz") and shutil.which(name)}}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (args.output / "source.patch").write_text(capture("git", "diff", "HEAD", "--", "src", "Cargo.toml", "Cargo.lock", "Makefile") or "")
    failed = False
    archive_hashes = {}
    with (args.output / "results.jsonl").open("w") as results:
        for index, source in enumerate(args.inputs):
            source = source.resolve()
            source_hash, size = digest(source), source.stat().st_size
            for codec in args.codecs:
                for repeat in range(args.repeats):
                    stem = f"{index}-{source.name}-{codec}-{repeat}"
                    archive, restored = (args.output / (stem + suffix) for suffix in (".archive", ".restored"))
                    external = codec in ("gzip", "bzip2", "xz")
                    if external:
                        flags = {"gzip": ["-n", "-9", "-c"], "bzip2": ["-9", "-c"], "xz": ["-9e", "-T1", "-c"]}[codec]
                        enc = [codec, *flags, str(source)]
                        dec = [codec, "-d", "-c", str(archive.resolve())]
                    else:
                        enc = [str(binary), "compress", "--no-progress", "--codec", codec, str(source), str(archive)]
                        dec = [str(binary), "decompress", "--no-progress", str(archive), str(restored)]
                    row = {"input": str(source), "input_bytes": size, "input_sha256": source_hash,
                           "codec": codec, "repeat": repeat, "roundtrip": False}
                    row["compress"] = measured(enc, args.output / (stem + ".compress.log"), args.timeout, archive if external else None)
                    if row["compress"]["status"] == "ok":
                        row["archive_bytes"] = archive.stat().st_size
                        row["archive_bpb"] = 8 * row["archive_bytes"] / size if size else None
                        row["archive_sha256"] = digest(archive)
                        key = (str(source), codec)
                        row["repeat_matches"] = archive_hashes.setdefault(key, row["archive_sha256"]) == row["archive_sha256"]
                        row["decompress"] = measured(dec, args.output / (stem + ".decompress.log"), args.timeout, restored if external else None)
                        row["roundtrip"] = (row["decompress"]["status"] == "ok" and restored.is_file()
                                            and restored.stat().st_size == size and digest(restored) == source_hash)
                        if row["roundtrip"]:
                            restored.unlink()  # Only this run's verified duplicate; archive/logs remain.
                    failed |= not row["roundtrip"] or not row.get("repeat_matches", True)
                    results.write(json.dumps(row) + "\n")
                    results.flush()
                    print(f"{source.name:16} {codec:16} {row.get('archive_bytes', '-'):>9} bytes  "
                          f"{row['compress']['wall_seconds']:8.3f}s  roundtrip={row['roundtrip']}", flush=True)
    if args.record:
        from benchmark_history import record
        record(args.output, args.record, args.note, args.manifest)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
