#!/usr/bin/env python3
"""Summarize current BITLSTM coding costs on accepted unchanged-archive traces."""
import argparse
import datetime
import json
from pathlib import Path
import re

import numpy as np

from benchmark import capture
from make_samples import digest
from cmix_bit_trace_support import inspect_log

ROOT = Path(__file__).resolve().parents[1]
ROW = np.dtype([("base", "<u2"), ("flags", "u1"), ("reserved", "u1"), ("features", "<f4", (14,))])


def coding_cost(base, head, flags):
    """Costs of the actual binary outcome, including integer discretization."""
    one = ((flags >> 1) & 1).astype(bool)
    pb = base.astype(np.float64) / 65536.0
    ph = head.astype(np.float64) / 65536.0
    if np.any((pb <= 0) | (pb >= 1) | (ph <= 0) | (ph >= 1)):
        raise ValueError("invalid discretized probability")
    return -np.log2(np.where(one, pb, 1 - pb)), -np.log2(np.where(one, ph, 1 - ph))


def aggregate(target, base, head, flags, select):
    n = int(np.count_nonzero(select))
    if not n:
        return
    target["bits"] += n
    target["overrides"] += int(np.count_nonzero(flags[select] & 1))
    target["base_bits"] += float(np.sum(base[select], dtype=np.float64))
    target["head_bits"] += float(np.sum(head[select], dtype=np.float64))
    target["helped_bits"] += int(np.count_nonzero(head[select] < base[select]))
    target["hurt_bits"] += int(np.count_nonzero(head[select] > base[select]))


def cell():
    return {"bits": 0, "overrides": 0, "base_bits": 0.0, "head_bits": 0.0, "helped_bits": 0, "hurt_bits": 0}


def summarize(args):
    parent = json.loads((args.comparison / "report.json").read_text())
    accepted = parent["variants"]["bit-trace-fixture"]
    if not all(accepted[k] for k in ("unchanged_archive", "trace_encoder_decoder_match", "original_bytes_roundtrip")):
        raise ValueError("requires accepted unchanged-archive tracing")
    run = args.run.resolve()
    if digest(run / "metadata.json") != accepted["metadata_sha256"]:
        raise ValueError("trace run metadata differs")
    directory = run / "trial-0-0"
    log = directory / "compress.log"
    if digest(log) != accepted["log_sha256"]["compress"]:
        raise ValueError("trace log differs")
    info = inspect_log(log, directory)
    if info != accepted["bit_trace"]:
        raise ValueError("trace files differ from accepted record")
    names = json.loads(re.findall(r'^CMIX_BITL_TRACE (\{[^\n]+\})$', log.read_text(), re.M)[0])
    n = info["bits"]
    trace = np.memmap(directory / names["trace"], dtype=ROW, mode="r", offset=28, shape=(n,))
    probability = np.memmap(directory / names["probability"], dtype="<u2", mode="r", shape=(n,))
    channel = np.memmap(directory / names["channel"], dtype="<f4", mode="r", offset=28, shape=(info["channels"], 69))
    cells = {"all": cell(), **{f"decile-{i}": cell() for i in range(10)},
             **{f"gate-{i}": cell() for i in range(2)}, **{f"zone-{i}": cell() for i in range(4)}}
    for start in range(0, n, 65536):
        end = min(start + 65536, n)
        rows = trace[start:end]
        indices = np.arange(start, end)
        aux = channel[indices // 8]
        base, head = coding_cost(rows["base"], probability[start:end], rows["flags"])
        partitions = {"decile": indices * 10 // n, "gate": (aux[:, 0] >= 0.5).astype(int),
                      "zone": aux[:, -1].astype(int)}
        aggregate(cells["all"], base, head, rows["flags"], np.ones(end-start, dtype=bool))
        for name, values in partitions.items():
            for value in np.unique(values):
                aggregate(cells[f"{name}-{value}"], base, head, rows["flags"], values == value)
    for value in cells.values():
        value["base_cost_bytes"] = value.pop("base_bits") / 8
        value["head_cost_bytes"] = value.pop("head_bits") / 8
        value["delta_cost_bytes"] = value["head_cost_bytes"] - value["base_cost_bytes"]
    report = {"kind": "bitl-current-coding-cost-summary", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)), "numpy_version": np.__version__,
              "comparison_sha256": digest(args.comparison / "report.json"), "trace": info,
              "archive_bytes": accepted["payload_bytes"], "input_sha256": parent["input_sha256"],
              "role": parent["role"], "groups": cells,
              "scope": "Sum of -log2 probability of the actual bit, from discretized live inputs/outputs, only where BITLSTM executes. Not an archive size or a no-head ablation; excludes other coded bits, termination and framing. Groups overlap. Gate/zone describe the channel captured every eight model bits; deciles divide model-bit count, not raw bytes. No calibration or new training."}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(cells["all"], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("comparison", "run", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    summarize(args)


if __name__ == "__main__":
    main()
