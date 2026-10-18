#!/usr/bin/env python3
"""Screen fixed structured-pruning recipes for model/payload tradeoffs.

This intentionally changes the model. Tensor reconstruction is checked, but
inference equivalence is neither expected nor claimed. Corpus round trips and
package/payload accounting are separate experiments.
"""
import argparse
import datetime
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

from weight_permutation import ENGINE, MANIFEST, upstream, wc, check_tensors
from competitive import differences, inventory
from make_samples import digest

RATES = (5, 10, 25)


def ranks(entries):
    arrays = {name: array for name, _, array in entries}
    result = {}
    for layer in range(16):
        prefix = f"blocks.{layer}.mlp."
        up = arrays[prefix + "up.weight.q"]
        down = arrays[prefix + "down.weight.q"]
        n = up.shape[0]
        if up.shape != (n, 192) or down.shape != (192, n) or not 0 < n <= 768:
            raise ValueError("unexpected MLP geometry")
        up_scale = wc._bf16_to_f32(arrays[prefix + "up.weight.scale"]).astype(np.float64)
        down_scale = wc._bf16_to_f32(arrays[prefix + "down.weight.scale"]).astype(np.float64)
        if up_scale.shape != (n,) or down_scale.shape != (192,):
            raise ValueError("unexpected per-row scale shape")
        if not np.isfinite(up_scale).all() or not np.isfinite(down_scale).all():
            raise ValueError("nonfinite model scale")
        # ReLU-squared makes the up-projection scale enter quadratically.
        # Layer-wide activation scales cancel when ranking within one layer.
        energy = (up.astype(np.float64) ** 2).sum(axis=1) * up_scale**2
        outgoing = np.sqrt(((down.astype(np.float64) * down_scale[:, None]) ** 2).sum(axis=0))
        score = energy * outgoing
        if not np.isfinite(score).all():
            raise ValueError("nonfinite pruning score")
        result[layer] = {"width": n, "scores": score.tolist(),
                         "rank": np.argsort(score, kind="stable").tolist()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    if protocol["rates_percent"] != list(RATES):
        raise ValueError("protocol differs from fixed pruning rates")
    frozen = json.loads(MANIFEST.read_text())
    if any(differences(frozen["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned source differs")
    original = ENGINE / protocol["weights_file"]
    if digest(original) != protocol["weights_sha256"]:
        raise ValueError("original model differs")
    output = args.output.resolve()
    if output.is_relative_to(ENGINE):
        raise ValueError("output must be outside pinned source")
    output.mkdir(parents=True, exist_ok=False)
    tensors, entries = upstream.read_container(str(original))
    identity = output / "identity.c4"
    wc.write_tensor_file_v4(str(identity), entries)
    if digest(identity) != digest(original):
        raise ValueError("writer fails original container identity")
    ranking = ranks(entries)
    (output / "rankings.json").write_text(json.dumps(ranking, indent=2) + "\n")
    dead, _ = upstream.dead_neurons(tensors)
    report = {"kind": "structured-pruning-container-screen", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "script_sha256": digest(Path(__file__)), "protocol_sha256": digest(args.protocol),
              "weights_sha256": digest(original), "original_container_bytes": original.stat().st_size,
              "platform": platform.platform(), "python": sys.version, "numpy": np.__version__,
              "upstream_pruning_script_sha256": digest(Path(upstream.__file__)),
              "upstream_writer_sha256": digest(Path(wc.__file__)),
              "identity_rewrite": True, "rankings_sha256": digest(output / "rankings.json"),
              "already_provably_dead_neurons": sum(len(row) for row in dead.values()),
              "variants": {},
              "scope": "Changed model, no inference-equivalence claim. Container savings exclude payload deterioration and executable changes; no prize score."}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    for rate in RATES:
        started = time.monotonic()
        removed = {layer: sorted(row["rank"][:row["width"] * rate // 100])
                   for layer, row in ranking.items()}
        candidate, rows, columns = upstream.prune(entries, removed)
        if rows != columns or rows != sum(len(row) for row in removed.values()):
            raise ValueError("incomplete paired row/column removal")
        path = output / f"mlp-prune{rate}.c4"
        wc.write_tensor_file_v4(str(path), candidate)
        check_tensors(candidate, wc.read_tensor_file_v3(str(path)))
        mapping = output / f"mlp-prune{rate}-removed.json"
        mapping.write_text(json.dumps(removed, separators=(",", ":")) + "\n")
        delta = path.stat().st_size - original.stat().st_size
        report["variants"][f"mlp-prune{rate}"] = {
            "container_bytes": path.stat().st_size, "container_sha256": digest(path),
            "delta_container_bytes": delta, "gross_two_container_delta_bytes": 2 * delta,
            "removed_neurons": rows, "removed_indices_sha256": digest(mapping),
            "widths": {str(layer): row["width"] - len(removed[layer]) for layer, row in ranking.items()},
            "tensor_roundtrip": True, "wall_seconds": time.monotonic() - started,
            "scope": "Retained tensors decode exactly; intentionally removed neurons change predictions."}
        save()
        print(f"mlp-prune{rate}: {path.stat().st_size:,} bytes, {delta:+,} per copy; {rows} neurons removed", flush=True)


if __name__ == "__main__":
    main()
