#!/usr/bin/env python3
"""Evaluate fixed extra CPU passes from the selected BITLSTM warm start."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time

from bitl_training import check_build, weight_info
from bitl_replay import BF16_SHA, new_output
from benchmark import capture
from make_samples import digest
import cmix_bit_trace_support as trace_support

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "prior", "build", "screen-run", "holdout-run",
                 "screen-replay", "holdout-replay", "shipped-weights", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    p = json.loads(args.protocol.read_text())
    if p["script_sha256"] != digest(Path(__file__)) or p["checkpoints"] != [2, 4, 8, 16] or p["learning_rate_1e6"] != 3000:
        raise ValueError("multi-pass recipe differs from frozen protocol")
    previous = json.loads((args.prior / "report.json").read_text())
    if (not previous["passed"] or not previous["eligible_for_archive_trial"]
            or digest(args.prior / "report.json") != p["prior_report_sha256"]
            or digest(args.prior / "selection.json") != previous["selection_sha256"]):
        raise ValueError("previous training result differs")
    selected = previous["selected_before_holdout"]
    prior_fp32 = args.prior / "lr3000-fp32.nblb"
    prior_bf16 = args.prior / "lr3000.nblb"
    if (weight_info(prior_fp32, 1) != selected["fp32"]
            or weight_info(prior_bf16, 2) != selected["bf16"]
            or selected["bf16"]["sha256"] != p["prior_model_sha256"]
            or digest(args.shipped_weights) != BF16_SHA):
        raise ValueError("starting models differ")
    build = check_build(args.build)
    if (build["kind"] != "bitl-public-training-build" or build["math_mode"] != "runtime"
            or digest(args.build / "build.json") != p["training_build_sha256"]
            or build["binary_sha256"] != previous["binary_sha256"]):
        raise ValueError("training binary differs")
    converter = ROOT / "engines/cmix-neif/training/bitl/tools/nblb.py"
    if digest(converter) != build["converter_sha256"]:
        raise ValueError("checkpoint converter differs")
    fixtures = {}
    for role in ("screen", "holdout"):
        replay_dir = getattr(args, role + "_replay")
        verified = json.loads((replay_dir / "report.json").read_text())
        run = getattr(args, role + "_run") / "trial-0-0"
        trace = trace_support.inspect_log(run / "compress.log", run)
        if (not verified["passed"] or digest(replay_dir / "report.json") != previous["references"][role]["replay_report_sha256"]
                or trace != previous["references"][role]["trace"]
                or trace["files"]["trace"]["sha256"] != p["trace_sha256"][role]):
            raise ValueError(role + " verified trace differs")
        names = json.loads(re.findall(r'^CMIX_BITL_TRACE (\{[^\n]+\})$', (run / "compress.log").read_text(), re.M)[0])
        fixtures[role] = (run / names["trace"], run / names["channel"], trace["bits"])
    out = new_output(args.output)
    shutil.copy2(args.protocol, out / "protocol.json")
    report = {"kind": "bitl-extra-pass-screen", "version": 1,
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "platform": platform.platform(), "script_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(args.protocol), "prior_report_sha256": digest(args.prior / "report.json"),
              "training_build_sha256": digest(args.build / "build.json"),
              "binary_sha256": build["binary_sha256"], "runs": [], "checkpoints": [], "passed": False,
              "scope": "Repeated full screen passes, with fresh Adam moments at each pass. Frozen BF16 selection on screen; only winner checked on reused disjoint fixture. Probability-cost diagnostic, not archive bytes or full-corpus validation."}
    save(out / "report.json", report)
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(("REPLAY_", "HUTTER_"))}

    def replay(label, role, weights, rate=None, target=None):
        trace, channel, bits = fixtures[role]
        env = {"REPLAY_CHANNEL": str(channel.resolve()), "REPLAY_LOAD": str(weights.resolve()), "REPLAY_SEED": "1112363057"}
        if rate is None:
            env["REPLAY_FREEZE_AT"] = "1"
        else:
            env.update(REPLAY_LR1E6=str(rate), REPLAY_DUMP=str(target.resolve()))
        command = [str((args.build / "replay").resolve()), str(trace.resolve()), "0", "0"]
        log = out / (label + ".log")
        start = time.monotonic()
        with log.open("wb") as f:
            result = subprocess.run(command, cwd=out, env={**clean_env, **env}, stdout=f, stderr=subprocess.STDOUT, timeout=1200)
        match = re.findall(r'^bits=(\d+) cells=\d+ inputs=\d+ params=\d+ base_B=([\d.]+) head_B=([\d.]+)', log.read_text(), re.M)
        record = {"label": label, "role": role, "command": command, "environment": env,
                  "wall_seconds": time.monotonic()-start, "exit_code": result.returncode,
                  "log_sha256": digest(log)}
        report["runs"].append(record)
        save(out / "report.json", report)
        if result.returncode or len(match) != 1 or int(match[0][0]) != bits:
            raise ValueError("incomplete replay: " + label)
        record.update(bits=bits, base_cost_bytes=float(match[0][1]), head_cost_bytes=float(match[0][2]))
        save(out / "report.json", report)
        return record

    prior_screen = replay("prior-screen", "screen", prior_bf16)
    fp32 = prior_fp32
    for pass_number in range(2, 17):
        target = out / f"pass{pass_number}-fp32.nblb"
        replay(f"train-pass{pass_number}", "screen", fp32, p["learning_rate_1e6"], target)
        full = weight_info(target, 1)
        fp32 = target
        if pass_number not in p["checkpoints"]:
            continue
        bf16 = out / f"pass{pass_number}.nblb"
        with (out / f"export-pass{pass_number}.log").open("wb") as f:
            subprocess.run(["python3", str(converter), "v2", str(fp32), str(bf16)], check=True, stdout=f, stderr=subprocess.STDOUT)
        compact = weight_info(bf16, 2)
        frozen = replay(f"evaluate-pass{pass_number}-screen", "screen", bf16)
        report["checkpoints"].append({"pass": pass_number, "fp32": full, "bf16": compact,
                                      "export_log_sha256": digest(out / f"export-pass{pass_number}.log"),
                                      "screen_cost_bytes": frozen["head_cost_bytes"],
                                      "delta_vs_one_pass_bytes": frozen["head_cost_bytes"]-prior_screen["head_cost_bytes"]})
        save(out / "report.json", report)
    winner = min(report["checkpoints"], key=lambda c: (c["screen_cost_bytes"], c["pass"]))
    report["selected_before_holdout"] = dict(winner)
    save(out / "selection.json", winner)
    report["selection_sha256"] = digest(out / "selection.json")
    report["screen_gate_passed"] = winner["delta_vs_one_pass_bytes"] <= -1.0
    if report["screen_gate_passed"]:
        old = replay("prior-holdout", "holdout", prior_bf16)
        new = replay("selected-holdout", "holdout", out / f"pass{winner['pass']}.nblb")
        report["holdout_delta_vs_one_pass_bytes"] = new["head_cost_bytes"]-old["head_cost_bytes"]
        report["holdout_gate_passed"] = report["holdout_delta_vs_one_pass_bytes"] <= -1.0
    else:
        report["holdout_gate_passed"] = False
    report["eligible_for_archive_trial"] = report["screen_gate_passed"] and report["holdout_gate_passed"]
    report["passed"] = True
    save(out / "report.json", report)
    print(json.dumps({k: report[k] for k in ("screen_gate_passed", "holdout_gate_passed", "eligible_for_archive_trial")}, indent=2))


if __name__ == "__main__":
    main()
