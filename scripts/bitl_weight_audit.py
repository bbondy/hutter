#!/usr/bin/env python3
"""Verify the shipped bit predictor's checkpoint, bf16 export and embedded bytes."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys

from benchmark import capture
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(differences(json.loads(MANIFEST.read_text())["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream differs")
    tree = ENGINE / "training/bitl"
    checkpoint = tree / "record/F2L_fp32.nblb"
    if digest(checkpoint) != "5447ed151f0503d7019ee23467d954842d128cf7e1cd4a3464c883155a022eb6":
        raise ValueError("checkpoint differs from published pass 32")
    output = args.output.resolve()
    if output.is_relative_to(ENGINE):
        raise ValueError("output must be outside pinned source")
    output.mkdir(parents=True, exist_ok=False)
    exported = output / "F2L.nblb"
    command = [sys.executable, str(tree / "tools/nblb.py"), "v2", str(checkpoint), str(exported)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    (output / "export.log").write_text(result.stdout + result.stderr)
    expected = "c72957f48c2ec81afa3aed2baae7acd964c17f96bb0406b8195818fc708a8e7d"
    if exported.stat().st_size != 7386 or digest(exported) != expected:
        raise ValueError("export differs from published bf16 model")
    header = ENGINE / "src/bit_head_weights.h"
    match = re.search(r'static const unsigned char kBlob\[7386\] = \{(.*?)\};', header.read_text(), re.S)
    if match is None:
        raise ValueError("embedded array changed")
    tokens = match[1].split(',')
    embedded = bytes(int(t.strip(), 16) for t in tokens if t.strip())
    if embedded != exported.read_bytes():
        raise ValueError("embedded model differs from exported checkpoint")
    data = checkpoint.read_bytes()
    if data[:4] != b"NBLB" or struct.unpack_from('<Iiiii', data, 4) != (1, 16, 89, 96, 28):
        raise ValueError("unexpected checkpoint geometry")
    params = struct.unpack('<3681f', data[24:])
    if not all(math.isfinite(x) for x in params):
        raise ValueError("nonfinite parameter")
    if any(params[row * 96 + col] != 0 for row in range(16) for col in range(90, 96)):
        raise ValueError("nonzero input padding")
    mark = dict(line.split('=', 1) for line in (tree / "record/mark.txt").read_text().splitlines())
    bits = int(mark["bits"])
    if (bits != 418837176 or bits % 8 or int(mark["trace_prefix_B"]) != 28 + bits * 60
            or int(mark["channel_prefix_B"]) != 28 + bits // 8 * 276):
        raise ValueError("inconsistent upstream trace geometry")
    report = {"kind": "bitl-checkpoint-export-audit", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)), "export_command": command,
              "checkpoint_bytes": len(data), "checkpoint_sha256": digest(checkpoint),
              "converter_sha256": digest(tree / "tools/nblb.py"),
              "header_sha256": digest(header), "bf16_bytes": len(embedded),
              "bf16_sha256": hashlib.sha256(embedded).hexdigest(),
              "embedded_matches_export": True, "finite_parameters": True, "padding_zero": True,
              "stored_values": 3681, "active_parameters": 3585,
              "geometry": {"cells": 16, "inputs_without_previous_bit": 89, "padded_width": 96, "stage1_width": 28},
              "published_training_bits": bits,
              "published_trace_prefix_bytes": int(mark["trace_prefix_B"]),
              "published_channel_prefix_bytes": int(mark["channel_prefix_B"]),
              "trace_mark_sha256": digest(tree / "record/mark.txt"),
              "missing": ["original trace and channel", "development tree containing the original trace writer"],
              "passed": True,
              "scope": "Exact checkpoint-to-bf16 export and embedded-byte audit. No training replay, regenerated trace, changed model or compression improvement is established."}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS: published 7,386-byte bf16 model equals checkpoint export and embedded array")


if __name__ == "__main__":
    main()
