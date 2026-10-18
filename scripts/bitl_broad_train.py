#!/usr/bin/env python3
"""Train on a separate article range, then select one BF16 model on screen."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

from benchmark import capture
from bitl_replay import BF16_SHA, new_output
from bitl_training import check_build, weight_info
import cmix_bit_trace_support as trace_support
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def checked_trace(run, verification, expected_report_hash):
    report = json.loads((verification / "report.json").read_text())
    if (digest(verification / "report.json") != expected_report_hash or not report["passed"]
            or not report["probabilities_match"] or not report["negative_control_rejected"]):
        raise ValueError("frozen replay verification differs")
    trial = run / "trial-0-0"
    info = trace_support.inspect_log(trial / "compress.log", trial)
    if info != report["trace"]:
        raise ValueError("accepted trace files changed")
    names = json.loads(re.findall(r'^CMIX_BITL_TRACE (\{[^\n]+\})$', (trial / "compress.log").read_text(), re.M)[0])
    return {"trace": trial / names["trace"], "channel": trial / names["channel"], "bits": info["bits"],
            "verification_sha256": expected_report_hash}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "build", "training-run", "training-replay",
                 "screen-run", "screen-replay", "holdout-run", "holdout-replay",
                 "shipped-weights", "prior-weights", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    p = json.loads(args.protocol.read_text())
    if (p["script_sha256"] != digest(Path(__file__))
            or p["learning_rates_1e6"] != [300, 1000, 3000]):
        raise ValueError("training recipe differs from frozen protocol")
    build = check_build(args.build)
    if (build["kind"] != "bitl-public-training-build" or build["math_mode"] != "runtime"
            or digest(args.build / "build.json") != p["training_build_sha256"]):
        raise ValueError("public trainer build differs")
    converter = ROOT / "engines/cmix-neif/training/bitl/tools/nblb.py"
    if digest(converter) != build["converter_sha256"]:
        raise ValueError("checkpoint converter differs")
    if (weight_info(args.shipped_weights, 2)["sha256"] != BF16_SHA
            or weight_info(args.prior_weights, 2)["sha256"] != p["prior_model_sha256"]):
        raise ValueError("model starting points differ")
    traces = {
        "training": checked_trace(args.training_run, args.training_replay, p["replay_report_sha256"]["training"]),
        "screen": checked_trace(args.screen_run, args.screen_replay, p["replay_report_sha256"]["screen"]),
        "holdout": checked_trace(args.holdout_run, args.holdout_replay, p["replay_report_sha256"]["holdout"]),
    }
    if traces["training"]["bits"] <= traces["screen"]["bits"]:
        raise ValueError("new training trace is not broader than the old screen")
    out = new_output(args.output)
    shutil.copy2(args.protocol, out / "protocol.json")
    report = {"kind": "bitl-separate-range-training", "version": 1,
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "platform": platform.platform(), "script_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(args.protocol), "training_build_sha256": digest(args.build / "build.json"),
              "binary_sha256": build["binary_sha256"], "traces": traces, "runs": [], "candidates": [],
              "passed": False,
              "scope": "One CPU pass per fixed rate on separate four-megabyte training range. Frozen BF16 screen selection, then one disjoint check. Probability costs only, not archive or prize bytes."}
    report["traces"] = {role: {"bits": t["bits"], "verification_sha256": t["verification_sha256"]}
                        for role, t in traces.items()}
    save(out / "report.json", report)
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(("REPLAY_", "HUTTER_"))}

    def replay(label, role, weights, rate=None, target=None):
        data = traces[role]
        env = {"REPLAY_CHANNEL": str(data["channel"].resolve()),
               "REPLAY_LOAD": str(weights.resolve()), "REPLAY_SEED": "1112363057"}
        if rate is None:
            env["REPLAY_FREEZE_AT"] = "1"
        else:
            env.update(REPLAY_LR1E6=str(rate), REPLAY_DUMP=str(target.resolve()))
        command = [str((args.build / "replay").resolve()), str(data["trace"].resolve()), "0", "0"]
        path = out / (label + ".log")
        start = time.monotonic()
        with path.open("wb") as f:
            result = subprocess.run(command, cwd=out, env={**clean_env, **env}, stdout=f,
                                    stderr=subprocess.STDOUT, timeout=1200)
        matches = re.findall(r'^bits=(\d+) cells=\d+ inputs=\d+ params=\d+ base_B=([\d.]+) head_B=([\d.]+)', path.read_text(), re.M)
        record = {"label": label, "role": role, "command": command, "environment": env,
                  "wall_seconds": time.monotonic()-start, "exit_code": result.returncode,
                  "log_sha256": digest(path)}
        report["runs"].append(record)
        save(out / "report.json", report)
        if result.returncode or len(matches) != 1 or int(matches[0][0]) != data["bits"]:
            raise ValueError("incomplete replay: " + label)
        record.update(bits=data["bits"], base_cost_bytes=float(matches[0][1]),
                      head_cost_bytes=float(matches[0][2]))
        save(out / "report.json", report)
        return record

    shipped_screen = replay("shipped-screen", "screen", args.shipped_weights)
    prior_screen = replay("prior-screen", "screen", args.prior_weights)
    for rate in p["learning_rates_1e6"]:
        fp32, bf16 = out / f"lr{rate}-fp32.nblb", out / f"lr{rate}.nblb"
        replay(f"train-lr{rate}", "training", args.shipped_weights, rate, fp32)
        full = weight_info(fp32, 1)
        with (out / f"export-lr{rate}.log").open("wb") as f:
            subprocess.run([sys.executable, str(converter), "v2", str(fp32), str(bf16)],
                           check=True, stdout=f, stderr=subprocess.STDOUT)
        compact = weight_info(bf16, 2)
        frozen = replay(f"evaluate-lr{rate}-screen", "screen", bf16)
        report["candidates"].append({"learning_rate_1e6": rate, "fp32": full, "bf16": compact,
                                     "export_log_sha256": digest(out / f"export-lr{rate}.log"),
                                     "screen_cost_bytes": frozen["head_cost_bytes"],
                                     "screen_delta_vs_shipped_bytes": frozen["head_cost_bytes"]-shipped_screen["head_cost_bytes"],
                                     "screen_delta_vs_prior_bytes": frozen["head_cost_bytes"]-prior_screen["head_cost_bytes"]})
        save(out / "report.json", report)
    winner = min(report["candidates"], key=lambda c: (c["screen_cost_bytes"], c["learning_rate_1e6"]))
    report["selected_before_holdout"] = dict(winner)
    save(out / "selection.json", winner)
    report["selection_sha256"] = digest(out / "selection.json")
    report["screen_gate_passed"] = winner["screen_delta_vs_prior_bytes"] <= -1.0
    if report["screen_gate_passed"]:
        prior_holdout = replay("prior-holdout", "holdout", args.prior_weights)
        selected_holdout = replay("selected-holdout", "holdout", out / f"lr{winner['learning_rate_1e6']}.nblb")
        report["holdout_delta_vs_prior_bytes"] = selected_holdout["head_cost_bytes"]-prior_holdout["head_cost_bytes"]
        report["holdout_gate_passed"] = report["holdout_delta_vs_prior_bytes"] <= -1.0
    else:
        report["holdout_gate_passed"] = False
    report["eligible_for_archive_trial"] = report["screen_gate_passed"] and report["holdout_gate_passed"]
    report["passed"] = True
    save(out / "report.json", report)
    print(json.dumps({k: report[k] for k in ("screen_gate_passed", "holdout_gate_passed", "eligible_for_archive_trial")}, indent=2))


if __name__ == "__main__":
    main()
