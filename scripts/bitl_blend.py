#!/usr/bin/env python3
"""Test a frozen interpolation between screen and separate-range BITLSTM weights."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time

from benchmark import capture
from bitl_broad_train import checked_trace, save
from bitl_replay import new_output
from bitl_training import check_build, weight_info
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("win", "bin", "wih", "whh", "bg", "wout", "bout")


def converter_module(path):
    spec = importlib.util.spec_from_file_location("pinned_bitl_nblb", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blend(left, right, numerator, denominator):
    if any(left[k] != right[k] for k in ("cells", "nin", "inw", "n1")):
        raise ValueError("checkpoint geometries differ")
    result = {k: left[k] for k in ("cells", "nin", "inw", "n1")}
    for key in KEYS:
        if len(left[key]) != len(right[key]):
            raise ValueError("checkpoint tensor lengths differ")
        result[key] = [(a * (denominator - numerator) + b * numerator) / denominator
                       for a, b in zip(left[key], right[key])]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "build", "screen-run", "screen-replay", "holdout-run",
                 "holdout-replay", "prior-weights", "broad-weights", "broad-report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    if (protocol["script_sha256"] != digest(Path(__file__))
            or protocol["blend_numerators"] != [1, 2, 3]
            or protocol["denominator"] != 4):
        raise ValueError("blend recipe differs from frozen protocol")
    build = check_build(args.build)
    if (build["kind"] != "bitl-public-training-build" or build["math_mode"] != "runtime"
            or digest(args.build / "build.json") != protocol["training_build_sha256"]):
        raise ValueError("public replay build differs")
    converter = ROOT / "engines/cmix-neif/training/bitl/tools/nblb.py"
    if digest(converter) != build["converter_sha256"]:
        raise ValueError("checkpoint converter differs")
    broad = json.loads(args.broad_report.read_text())
    if (digest(args.broad_report) != protocol["broad_report_sha256"]
            or not broad["passed"] or broad["eligible_for_archive_trial"]
            or broad["selected_before_holdout"]["learning_rate_1e6"] != 3000):
        raise ValueError("separate-range source checkpoint differs")
    prior_info = weight_info(args.prior_weights, 2)
    broad_info = weight_info(args.broad_weights, 2)
    if (prior_info["sha256"] != protocol["prior_model_sha256"]
            or broad_info["sha256"] != protocol["broad_model_sha256"]
            or broad_info != broad["selected_before_holdout"]["bf16"]):
        raise ValueError("frozen endpoint weights differ")
    traces = {role: checked_trace(getattr(args, role + "_run"), getattr(args, role + "_replay"),
                                  protocol["replay_report_sha256"][role])
              for role in ("screen", "holdout")}
    out = new_output(args.output)
    shutil.copy2(args.protocol, out / "protocol.json")
    nblb = converter_module(converter)
    left, right = nblb.read(args.prior_weights), nblb.read(args.broad_weights)
    for label, values, expected in (("prior", left, prior_info), ("broad", right, broad_info)):
        endpoint = out / (label + "-roundtrip.nblb")
        nblb.write_v2(endpoint, values)
        if weight_info(endpoint, 2) != expected:
            raise ValueError("checkpoint converter changed endpoint bytes")
        endpoint.unlink()
    report = {"kind": "bitl-frozen-checkpoint-blend", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "platform": platform.platform(), "script_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(args.protocol), "build_sha256": digest(args.build / "build.json"),
              "converter_sha256": digest(converter), "prior": prior_info, "broad": broad_info,
              "traces": {role: {"bits": value["bits"], "verification_sha256": value["verification_sha256"]}
                         for role, value in traces.items()},
              "runs": [], "candidates": [], "passed": False,
              "scope": "Three predeclared BF16 interpolations; frozen screen selects once, one disjoint replay if the screen gate passes. Probability costs only, no archive or prize bytes."}
    save(out / "report.json", report)
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(("REPLAY_", "HUTTER_"))}

    def evaluate(label, role, weights):
        data = traces[role]
        env = {"REPLAY_CHANNEL": str(data["channel"].resolve()),
               "REPLAY_LOAD": str(weights.resolve()), "REPLAY_SEED": "1112363057",
               "REPLAY_FREEZE_AT": "1"}
        command = [str((args.build / "replay").resolve()), str(data["trace"].resolve()), "0", "0"]
        log = out / (label + ".log")
        start = time.monotonic()
        with log.open("wb") as file:
            result = subprocess.run(command, cwd=out, env={**clean_env, **env}, stdout=file,
                                    stderr=subprocess.STDOUT, timeout=1200)
        matches = re.findall(r'^bits=(\d+) cells=\d+ inputs=\d+ params=\d+ base_B=([\d.]+) head_B=([\d.]+)',
                             log.read_text(), re.M)
        row = {"label": label, "role": role, "command": command, "environment": env,
               "wall_seconds": time.monotonic() - start, "exit_code": result.returncode,
               "log_sha256": digest(log)}
        report["runs"].append(row)
        save(out / "report.json", report)
        if result.returncode or len(matches) != 1 or int(matches[0][0]) != data["bits"]:
            raise ValueError("incomplete frozen replay: " + label)
        row.update(bits=data["bits"], base_cost_bytes=float(matches[0][1]),
                   head_cost_bytes=float(matches[0][2]))
        save(out / "report.json", report)
        return row

    prior_screen = evaluate("prior-screen", "screen", args.prior_weights)
    for numerator in protocol["blend_numerators"]:
        weights = out / f"blend-{numerator}-of-4.nblb"
        nblb.write_v2(weights, blend(left, right, numerator, 4))
        info = weight_info(weights, 2)
        row = evaluate(f"blend-{numerator}-screen", "screen", weights)
        report["candidates"].append({"numerator": numerator, "denominator": 4,
                                     "bf16": info, "screen_cost_bytes": row["head_cost_bytes"],
                                     "screen_delta_vs_prior_bytes": row["head_cost_bytes"] - prior_screen["head_cost_bytes"]})
        save(out / "report.json", report)
    winner = min(report["candidates"], key=lambda x: (x["screen_cost_bytes"], x["numerator"]))
    report["selected_before_holdout"] = dict(winner)
    save(out / "selection.json", winner)
    report["selection_sha256"] = digest(out / "selection.json")
    report["screen_gate_passed"] = winner["screen_delta_vs_prior_bytes"] <= -1.0
    if report["screen_gate_passed"]:
        prior_holdout = evaluate("prior-holdout", "holdout", args.prior_weights)
        selected = evaluate("selected-holdout", "holdout", out / f"blend-{winner['numerator']}-of-4.nblb")
        report["holdout_delta_vs_prior_bytes"] = selected["head_cost_bytes"] - prior_holdout["head_cost_bytes"]
        report["holdout_gate_passed"] = report["holdout_delta_vs_prior_bytes"] <= -1.0
    else:
        report["holdout_gate_passed"] = False
    report["eligible_for_archive_trial"] = report["screen_gate_passed"] and report["holdout_gate_passed"]
    report["passed"] = True
    save(out / "report.json", report)
    print(json.dumps({k: report[k] for k in ("screen_gate_passed", "holdout_gate_passed",
                                              "eligible_for_archive_trial")}, indent=2))


if __name__ == "__main__":
    main()
