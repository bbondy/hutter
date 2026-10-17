#!/usr/bin/env python3
"""Keep small, immutable benchmark records in Git and compare matched trials."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "runs"


def record(run, run_id, note, manifest=None, root=ROOT):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id):
        raise ValueError("run ID must contain only letters, numbers, dot, underscore or dash")
    metadata = json.loads((run / "metadata.json").read_text())
    rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
    if not rows:
        raise ValueError("cannot record an empty run")
    for row in rows:
        if not all(key in row for key in ("input_sha256", "input_bytes", "codec", "compress", "roundtrip")):
            raise ValueError("incomplete benchmark row")
    if manifest:
        known = {s["sha256"]: s["bytes"] for s in json.loads(manifest.read_text())["samples"]}
        if any(known.get(row["input_sha256"]) != row["input_bytes"] for row in rows):
            raise ValueError("manifest does not describe every benchmark input")
    target = root / run_id
    target.mkdir(parents=True, exist_ok=False)
    for name in ("metadata.json", "results.jsonl", "source.patch"):
        if (run / name).exists():
            shutil.copyfile(run / name, target / name)
    if manifest:
        shutil.copyfile(manifest, target / "samples.json")
    (target / "record.json").write_text(json.dumps({
        "id": run_id, "note": note, "source_run": str(run.resolve()),
        "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trials": len(rows), "verified_trials": sum(r["roundtrip"] for r in rows),
        "commit": metadata.get("commit"),
    }, indent=2) + "\n")
    print(f"Recorded {len(rows)} trials in {target}; commit this directory to retain them.")
    return target


def aggregates(run):
    groups = {}
    for line in (run / "results.jsonl").read_text().splitlines():
        row = json.loads(line)
        key = (row["input_sha256"], row["codec"])
        groups.setdefault(key, []).append(row)
    result = {}
    for key, rows in groups.items():
        if any(not r["roundtrip"] or not r.get("repeat_matches", True) for r in rows):
            continue
        if len({r["archive_sha256"] for r in rows}) != 1:
            continue
        result[key] = {
            "input": Path(rows[0]["input"]).name, "codec": key[1], "n": len(rows),
            "bytes": rows[0]["archive_bytes"],
            "compress_s": statistics.median(r["compress"]["wall_seconds"] for r in rows),
            "decompress_s": statistics.median(r["decompress"]["wall_seconds"] for r in rows),
            "rss": max((r[phase]["peak_rss_bytes"] or 0) for r in rows for phase in ("compress", "decompress")),
        }
    return result


def compare(before, after):
    old, new = aggregates(before), aggregates(after)
    keys = sorted(old.keys() & new.keys(), key=lambda k: (old[k]["input"], k[1]))
    if not keys:
        raise ValueError("no matching verified input SHA-256 + codec pairs")
    meta_old, meta_new = [json.loads((p / "metadata.json").read_text()) for p in (before, after)]
    print("Negative deltas are improvements. Only exact input SHA-256 + codec matches are compared.")
    if any(meta_old.get(k) != meta_new.get(k) for k in ("cpu", "platform", "machine")):
        print("WARNING: machines/platforms differ; time and memory deltas are not controlled comparisons.")
    if any(old[k]["n"] < 3 or new[k]["n"] < 3 for k in keys):
        print("Timing is exploratory: at least one result has fewer than three repeats.")
    print("| Input | Codec | Before bytes | After bytes | Delta bytes | Delta % | Compress delta s | Decompress delta s | Peak RSS delta MB |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for key in keys:
        a, b = old[key], new[key]
        delta = b["bytes"] - a["bytes"]
        pct = 100 * delta / a["bytes"] if a["bytes"] else 0
        print(f"| {a['input']} | {a['codec']} | {a['bytes']} | {b['bytes']} | {delta:+d} | {pct:+.3f}% | "
              f"{b['compress_s']-a['compress_s']:+.3f} | {b['decompress_s']-a['decompress_s']:+.3f} | {(b['rss']-a['rss'])/1e6:+.2f} |")
    skipped = len(old.keys() | new.keys()) - len(keys)
    print(f"Compared {len(keys)} pairs; {skipped} verified pairs present in only one run. Failed/nonrepeatable groups are excluded.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    save = sub.add_parser("record")
    save.add_argument("run", type=Path)
    save.add_argument("--id", required=True)
    save.add_argument("--note", required=True)
    save.add_argument("--manifest", type=Path)
    sub.add_parser("list")
    diff = sub.add_parser("compare")
    diff.add_argument("before")
    diff.add_argument("after")
    args = parser.parse_args()
    try:
        if args.command == "record":
            record(args.run, args.id, args.note, args.manifest, args.root)
        elif args.command == "list":
            for path in sorted(args.root.glob("*/record.json")):
                row = json.loads(path.read_text())
                print(f"{row['id']}  {row['verified_trials']}/{row['trials']} verified  {row['commit'][:12]}  {row['note']}")
        else:
            compare(args.root / args.before, args.root / args.after)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
