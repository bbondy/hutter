#!/usr/bin/env python3
"""Generate byte-exact, reproducible development slices; never normalize XML."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", default=Path("data/enwik8"))
    parser.add_argument("--output", type=Path, default=Path("data/samples"))
    args = parser.parse_args()
    known = {
        100_000_000: "57b8363b814821dc9d47aa4d41f58733519076b2",
        1_000_000_000: "2996e86fb978f93cca8f566cc56998923e7fe581",
    }
    size = args.source.stat().st_size
    if size not in known or digest(args.source, "sha1") != known[size]:
        parser.error("source must be checksum-verified official enwik8 or enwik9")
    # Prefixes measure model warm-up; disjoint slices expose prefix-only wins.
    specs = [
        ("prefix-100k", 0, 100_000, "screen"),
        ("prefix-1m", 0, 1_000_000, "development"),
        ("middle-1m", 49_000_000, 1_000_000, "development"),
        ("tail-1m", 89_000_000, 1_000_000, "confirmation"),
        ("prefix-10m", 0, 10_000_000, "promotion"),
    ]
    if size == 1_000_000_000:
        specs += [(f"region-{i}-1m", i * 100_000_000, 1_000_000,
                   "development" if i % 2 else "confirmation") for i in range(1, 10)]
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "source": str(args.source), "source_bytes": size,
                "source_sha1": known[size], "source_sha256": digest(args.source),
                "samples": []}
    with args.source.open("rb") as source:
        for name, offset, length, role in specs:
            source.seek(offset)
            data = source.read(length)
            assert len(data) == length
            path = args.output / name
            path.write_bytes(data)
            manifest["samples"].append({"path": str(path), "offset": offset,
                                        "bytes": length, "role": role,
                                        "sha256": hashlib.sha256(data).hexdigest()})
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified source; wrote {len(specs)} samples and {args.output / 'manifest.json'}")


if __name__ == "__main__":
    main()
