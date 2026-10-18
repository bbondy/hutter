#!/usr/bin/env python3
"""Attribute the unchanged weight container's bytes to tensors and families.

The upstream writer is observed without changing its source or coding rules.
Pending range-coder bytes are counted at tensor boundaries; the final flush and
file header are reported separately. Empirical entropy is diagnostic, not an
achievable compressed size (it excludes a decoder and distribution parameters).
"""
import argparse
from collections import defaultdict
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

from weight_permutation import ENGINE, MANIFEST, EXPORT, wc, upstream
from competitive import differences, inventory
from make_samples import digest


def entropy_bytes(values):
    counts = np.bincount(values.astype(np.int16).ravel() + 7, minlength=15)
    counts = counts[counts > 0].astype(np.float64)
    return float(-(counts * np.log2(counts / counts.sum())).sum() / 8) if len(counts) else 0.0


class ObservedEntries(list):
    def __init__(self, entries):
        super().__init__(entries)
        self.records = []

    def __iter__(self):
        frame = inspect.currentframe().f_back
        try:
            if frame.f_code is not wc.write_tensor_file_v3.__code__:
                raise ValueError("observer must be called directly by the pinned writer")
            enc = frame.f_locals["enc"]
            for name, code, array in list.__iter__(self):
                before = len(enc.out) + enc.cache_size
                yield name, code, array
                after = len(enc.out) + enc.cache_size
                row = {"name": name, "dtype_code": code, "shape": list(array.shape),
                       "raw_bytes": array.nbytes, "coded_bytes": after - before,
                       "encoding": frame.f_locals["encoding"]}
                if row["encoding"] == wc.ENC_INT4:
                    matrix = array.reshape(array.shape[0] if array.ndim > 1 else 1, -1)
                    active = matrix[np.any(matrix, axis=1)]
                    row.update({"zero_rows": len(matrix) - len(active),
                                "coded_values": active.size,
                                "empirical_tensor_entropy_bytes": entropy_bytes(active),
                                "empirical_row_entropy_bytes": sum(entropy_bytes(r) for r in active)})
                self.records.append(row)
        finally:
            del frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads(MANIFEST.read_text())
    if any(differences(frozen["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream tree differs")
    original = ENGINE / "weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4"
    output = args.output.resolve()
    if output.is_relative_to(ENGINE):
        raise ValueError("audit output must be outside upstream")
    output.mkdir(parents=True, exist_ok=False)
    _, entries = upstream.read_container(str(original))
    observed = ObservedEntries(entries)
    rewritten = output / "identity.c4"
    wc.write_tensor_file_v4(str(rewritten), observed)
    if digest(rewritten) != digest(original) or len(observed.records) != len(entries):
        raise ValueError("observed writer did not reproduce every original container byte")
    groups = defaultdict(lambda: defaultdict(float))
    for row in observed.records:
        family = re.sub(r"^blocks\.\d+\.", "blocks.*.", row["name"])
        for key in ("coded_bytes", "raw_bytes", "coded_values", "zero_rows",
                    "empirical_tensor_entropy_bytes", "empirical_row_entropy_bytes"):
            if key in row:
                groups[family][key] += row[key]
    attributed = sum(row["coded_bytes"] for row in observed.records)
    overhead = original.stat().st_size - attributed
    if overhead != 17:  # 12-byte magic/count header and five range-coder flush bytes.
        raise ValueError("unexpected accounting remainder: " + str(overhead))
    report = {"kind": "unchanged-weight-container-audit", "version": 1,
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "script_sha256": digest(Path(__file__)), "numpy": np.__version__, "python": sys.version,
              "upstream_writer_sha256": digest(EXPORT / "weights_compress_v3.py"),
              "container_sha256": digest(original), "container_bytes": original.stat().st_size,
              "identity_rewrite": True, "tensor_count": len(entries),
              "attributed_tensor_bytes": attributed, "header_and_flush_bytes": overhead,
              "families": dict(sorted(groups.items(), key=lambda item: -item[1]["coded_bytes"])),
              "tensors": observed.records,
              "scope": "Observed upstream coding including per-tensor metadata. Empirical entropy fits each tensor/row to itself, excludes model costs and is not an achievable size or a prize score."}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for name, row in list(report["families"].items())[:12]:
        print(f'{int(row["coded_bytes"]):9,d} bytes  {name}')
    print("Header and final flush:", overhead, "bytes; exact original container reproduced")


if __name__ == "__main__":
    main()
