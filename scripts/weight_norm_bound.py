#!/usr/bin/env python3
"""Audit an idealized RMS-aware dead-neuron bound, without modifying weights.

This is a feasibility diagnostic. Floating-point normalization, compiler
semantics and nonfinite states need separate treatment before any safe-pruning
claim. A safety factor in this report is exploratory headroom, not that proof.
"""
import argparse
import datetime
import json
from pathlib import Path

import numpy as np

from benchmark import capture
from competitive import differences, inventory
from make_samples import digest
from weight_permutation import ENGINE, MANIFEST, ROOT, upstream, wc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads(MANIFEST.read_text())
    if any(differences(frozen["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned source differs")
    weights = ENGINE / "weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4"
    if digest(weights) != "ba982cd5da95c88c076d63b7767dad12e0c510ea3dd99adc0e213e707b45e719":
        raise ValueError("model differs")
    tensors, entries = upstream.read_container(str(weights))
    arrays = {n: a for n, _, a in entries}
    dead, _ = upstream.dead_neurons(tensors)
    report = {"kind": "idealized-rms-dead-neuron-feasibility", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)), "weights_sha256": digest(weights),
              "numpy_version": np.__version__, "layers": {},
              "formula": "abs(float32(s_act*w_scale)) * (sqrt(192)*norm2(up_int4)/s_act + 0.5*norm1(up_int4))",
              "reason": "In exact real arithmetic, RMS normalization with nonnegative epsilon bounds norm2(xn) by sqrt(192). Rounding each scaled coordinate changes its absolute value by at most 0.5; clipping cannot increase it. Cauchy-Schwarz then bounds the weighted absolute sum. A result below sqrt(0.5*s_next) could justify investigating a stronger dead-neuron proof.",
              "scope": "No candidate written, predictions measured or compression improvement claimed. Idealized bound only; floating-point error, compiler semantics and nonfinite states are not certified."}
    for layer in range(16):
        p = f"blocks.{layer}.mlp."
        q = arrays[p + "up.weight.q"].astype(np.float64)
        scale = wc._bf16_to_f32(arrays[p + "up.weight.scale"])
        sa = float(wc._bf16_to_f32(arrays[p + "up.quantize_activation.scale"])[0])
        sn = float(wc._bf16_to_f32(arrays[p + "down.quantize_activation.scale"])[0])
        if q.shape[1] != 192 or sa <= 0 or sn <= 0 or not np.isfinite(scale).all():
            raise ValueError("unexpected geometry or scales")
        fold = np.abs((np.float32(sa) * scale).astype(np.float64))
        bound = fold * (np.sqrt(192) * np.linalg.norm(q, axis=1) / sa + 0.5 * np.abs(q).sum(axis=1))
        ratio = bound / np.sqrt(0.5 * sn)
        if not np.isfinite(ratio).all():
            raise ValueError("nonfinite bound")
        report["layers"][str(layer)] = {
            "width": len(q), "upstream_dead": dead[layer],
            "idealized_candidates": np.flatnonzero(ratio < 1).tolist(),
            "with_0_1_percent_headroom": np.flatnonzero(ratio * 1.001 < 1).tolist(),
            "minimum_bound_to_threshold": float(ratio.min()),
            "median_bound_to_threshold": float(np.median(ratio)),
            "ratio_by_neuron": ratio.tolist()}
    report["upstream_dead_count"] = sum(len(v) for v in dead.values())
    report["idealized_candidate_count"] = sum(len(v["idealized_candidates"]) for v in report["layers"].values())
    report["decision"] = ("No additional candidate under this bound; do not develop a pruning change from it."
                          if report["idealized_candidate_count"] == report["upstream_dead_count"] else
                          "Investigate floating-point-safe bounds and actual kernels before removing any candidate. This audit alone authorizes no equivalence claim.")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["decision"], report["idealized_candidate_count"], flush=True)


if __name__ == "__main__":
    main()
