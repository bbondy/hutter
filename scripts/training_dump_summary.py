#!/usr/bin/env python3
"""Summarize verified upstream training rows without loading the full dump into RAM."""
import argparse
import datetime
import json
from pathlib import Path
import struct

import numpy as np

from make_samples import digest
from training_dump import DUMP

ROW = np.dtype([("src", "<i4"), ("tok", "u1"), ("prev1", "u1"), ("prev2", "u1"),
                ("match_byte", "u1"), ("match_class", "u1"), ("flags", "u1"), ("reserved", "<u2")])
FLAGS = ("inserted", "masked", "document_start", "redirect", "prior0", "alias_or_author", "author", "metadata_prompt")


def summarize(build, output):
    source = json.loads((build / "report.json").read_text())
    if source["kind"] != "upstream-training-row-dump-reproduction" or not source["passed"]:
        raise ValueError("requires a verified complete training-row dump")
    for name, record in source["outputs"].items():
        file = build / "run" / name
        if file.stat().st_size != record["bytes"] or digest(file) != record["sha256"]:
            raise ValueError("diagnostic data differs: " + name)
    dump = build / "run/paket-zeilen.bin"
    if source["outputs"][dump.name] != {"bytes": DUMP[0], "sha256": DUMP[1]}:
        raise ValueError("dump differs from the frozen published reference")
    with dump.open("rb") as file:
        header = file.read(12)
    if header != struct.pack("<i", -2) + b"PKD" + bytes((2, 12, 8, 0, 0)):
        raise ValueError("unexpected row-dump header")
    rows = np.memmap(dump, dtype=ROW, mode="r", offset=12)
    n = len(rows)
    counts = {key: 0 for key in FLAGS}
    counts.update(stream_rows=0, inserted_rows=0, unmasked_rows=0,
                  alias_rows_excluding_author=0, unmasked_alias_rows_excluding_author=0)
    documents, previous_src, monotonic = [], -1, True
    token_max, reserved_nonzero, unknown_source_rows = 0, 0, 0
    chunk = 1 << 20
    for start in range(0, n, chunk):
        block = rows[start:start + chunk]
        flags = block["flags"]
        for bit, key in enumerate(FLAGS):
            counts[key] += int(np.count_nonzero(flags & (1 << bit)))
        stream = block["src"][block["src"] >= 0]
        if len(stream):
            monotonic &= bool(stream[0] > previous_src and np.all(stream[1:] > stream[:-1]))
            previous_src = int(stream[-1])
        counts["stream_rows"] += len(stream)
        counts["inserted_rows"] += int(np.count_nonzero(block["src"] == -1))
        counts["unmasked_rows"] += int(np.count_nonzero((flags & 2) == 0))
        aliases = ((flags & 32) != 0) & ((flags & 64) == 0)
        counts["alias_rows_excluding_author"] += int(np.count_nonzero(aliases))
        counts["unmasked_alias_rows_excluding_author"] += int(np.count_nonzero(aliases & ((flags & 2) == 0)))
        documents.extend((np.flatnonzero(flags & 4) + start).tolist())
        token_max = max(token_max, int(block["tok"].max()))
        reserved_nonzero += int(np.count_nonzero(block["reserved"]))
        unknown_source_rows += int(np.count_nonzero(block["src"] < -1))
    if (not monotonic or previous_src != 552750203 or token_max >= 208
            or reserved_nonzero or unknown_source_rows):
        raise ValueError("unexpected row ordering, tail, token or reserved field")
    lengths = np.diff(np.array(documents + [n], dtype=np.int64))
    if not documents or documents[0] != 0 or np.any(lengths <= 0):
        raise ValueError("document-start flags do not partition the row sequence")
    zone = np.memmap(build / "run/zonenmaske.u8", dtype=np.uint8, mode="r")
    histogram = np.zeros(256, dtype=np.int64)
    for start in range(0, len(zone), chunk):
        histogram += np.bincount(zone[start:start + chunk], minlength=256)
    report = {"kind": "training-row-coverage-summary", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "script_sha256": digest(Path(__file__)), "numpy_version": np.__version__,
              "parent_dump_report_sha256": digest(build / "report.json"),
              "dump": source["outputs"][dump.name], "rows_excluding_header": n,
              "counts": counts, "strictly_increasing_stream_positions": bool(monotonic),
              "last_stream_position": previous_src,
              "documents": {"count": len(documents), "minimum_rows": int(lengths.min()),
                            "median_rows": float(np.median(lengths)), "maximum_rows": int(lengths.max()),
                            "rows_before_first_document": documents[0]},
              "zone_counts": {str(i): int(value) for i, value in enumerate(histogram) if value},
              "scope": "Coverage of upstream input/training rows, not measured coding loss or an activation-importance estimate. Unmasked alias rows identify potential refresh targets; they do not measure their value in the final mixture."}
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.dump_build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
