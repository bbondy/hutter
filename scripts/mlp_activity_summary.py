#!/usr/bin/env python3
"""Summarize archive-preserving activity probes and the prior rejected removals."""
import argparse
import datetime
import json
from pathlib import Path

import numpy as np

from cmix_activity_support import parse_log
from make_samples import digest
from weight_permutation import ENGINE, upstream, wc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--pruning-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = args.comparison / "report.json"
    comparison = json.loads(parent.read_text())
    activity = comparison["variants"]["activity-mlp"]
    baseline = comparison["variants"]["baseline"]
    if (not activity["unchanged_archive"] or not activity["activity_encoder_decoder_match"]
            or activity["archive_sha256"] != baseline["archive_sha256"]
            or activity["payload_bytes"] != baseline["payload_bytes"]
            or not activity["original_bytes_roundtrip"]):
        raise ValueError("requires a verified archive-preserving activity comparison")
    rows = activity["activity"]
    for phase in ("compress", "decompress"):
        log = args.comparison / ("activity-mlp-" + phase + ".log")
        if digest(log) != activity["log_sha256"][phase] or parse_log(log) != rows:
            raise ValueError("activity evidence differs")
    weights = ENGINE / "weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4"
    expected = comparison["side_data"][weights.name]
    if weights.stat().st_size != expected["bytes"] or digest(weights) != expected["sha256"]:
        raise ValueError("model differs from activity run")
    _, entries = upstream.read_container(str(weights))
    arrays = {n: a for n, _, a in entries}
    pruning_path = args.pruning_record / "report.json"
    pruning = json.loads(pruning_path.read_text())
    if pruning["weights_sha256"] != digest(weights):
        raise ValueError("prior pruning experiment used different original weights")
    removed = {}
    for name, record in pruning["variants"].items():
        path = args.pruning_record / (name + "-removed.json")
        if digest(path) != record["removed_indices_sha256"]:
            raise ValueError("prior removal map differs")
        removed[name] = json.loads(path.read_text())
    report = {"kind": "mlp-activity-summary", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "script_sha256": digest(Path(__file__)), "numpy_version": np.__version__,
              "comparison_sha256": digest(parent), "pruning_report_sha256": digest(pruning_path),
              "role": comparison["role"], "input_sha256": comparison["input_sha256"],
              "weights_sha256": digest(weights), "layers": {},
              "single_neuron_score": "mean(q_i^2) * sum_o((down_int4[o,i] * down_row_scale[o] * down_activation_scale)^2)",
              "scope": "Actual quantized activations on reused fixtures, including inserted prompts and adaptive-depth skips. The score estimates squared residual contribution from one isolated neuron, not coding loss. Sums of these scores omit cross-neuron correlations. No new pruning candidate, universal deadness, full-corpus estimate or prize gain is claimed."}
    for row in rows:
        layer, width, calls = row["layer"], row["width"], row["calls"]
        count = np.array(row["count"], dtype=np.int64)
        squared = np.array(row["sumsq"], dtype=np.float64)
        p = f"blocks.{layer}.mlp.down."
        down = arrays[p + "weight.q"].astype(np.float64)
        scale = wc._bf16_to_f32(arrays[p + "weight.scale"]).astype(np.float64)
        sa = float(wc._bf16_to_f32(arrays[p + "quantize_activation.scale"])[0])
        if down.shape != (192, width) or not np.isfinite(scale).all() or sa <= 0:
            raise ValueError("unexpected model geometry or scale")
        column_energy = np.sum((down * (scale * sa)[:, None])**2, axis=0)
        score = squared / calls * column_energy
        if not np.isfinite(score).all() or squared.sum() <= 0 or score.sum() <= 0:
            raise ValueError("empty or nonfinite activation energy")
        prior = {}
        for name, indices in removed.items():
            drop = indices[str(layer)]
            if drop != sorted(set(drop)) or not drop or min(drop) < 0 or max(drop) >= width:
                raise ValueError("invalid removal map")
            prior[name] = {"removed_neurons": len(drop),
                           "observed_inactive_removed": int(np.count_nonzero(count[drop] == 0)),
                           "activation_squared_mass_fraction": float(squared[drop].sum() / squared.sum()),
                           "sum_single_neuron_score_fraction": float(score[drop].sum() / score.sum())}
        report["layers"][str(layer)] = {
            "width": width, "executed_calls": calls,
            "mean_active_neurons_per_call": float(count.sum() / calls),
            "observed_inactive_indices": np.flatnonzero(count == 0).tolist(),
            "activation_frequency_minimum": float(count.min() / calls),
            "activation_frequency_median": float(np.median(count) / calls),
            "activation_frequency_maximum": float(count.max() / calls),
            "single_neuron_score_by_index": score.tolist(), "prior_rejected_removals": prior}
    report["observed_inactive_total"] = sum(len(r["observed_inactive_indices"]) for r in report["layers"].values())
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(comparison["role"], "observed inactive neurons:", report["observed_inactive_total"])


if __name__ == "__main__":
    main()
