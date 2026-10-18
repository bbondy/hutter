#!/usr/bin/env python3
"""Small, gated CPU warm-start experiment using the public BITLSTM trainer."""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import time

from benchmark import capture
from bitl_replay import BF16_SHA, new_output
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
import cmix_bit_trace_support as trace_support

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def provenance(kind):
    return {"kind": kind, "version": 1, "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
            "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "script_sha256": digest(Path(__file__)), "platform": platform.platform(), "passed": False}


def check_build(path):
    record = json.loads((path / "build.json").read_text())
    if (not record["passed"] or record["platform"] != platform.platform()
            or digest(path / "replay") != record["binary_sha256"]
            or inventory(path / "source") != record["source_files"]):
        raise ValueError("trainer build changed or belongs to another platform")
    return record


def build(args):
    if any(differences(json.loads(MANIFEST.read_text())["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream differs")
    parent = args.replay_build.resolve()
    if args.output.resolve().is_relative_to(parent):
        raise ValueError("training build must be outside its parent replay build")
    previous = check_build(parent)
    if previous["kind"] != "bitl-frozen-replay-build":
        raise ValueError("requires a recorded replay verifier build")
    out = new_output(args.output)
    shutil.copytree(parent / "source", out / "source")
    # Restore the original public driver. Model arithmetic and platform support
    # remain exactly those of the separately checked replay build.
    driver = ENGINE / "training/bitl/trainer/replay_trainer.cpp"
    shutil.copy2(driver, out / "source/replay_trainer.cpp")
    command = [a.replace(str(parent), str(out)) for a in previous["command"]]
    info = {**provenance("bitl-public-training-build"), "parent_build_sha256": digest(parent / "build.json"),
            "compiler": previous["compiler"], "command": command, "source_files": inventory(out / "source"),
            "driver_sha256": digest(driver), "converter_sha256": digest(ENGINE / "training/bitl/tools/nblb.py")}
    save(out / "build.json", info)
    with (out / "build.log").open("wb") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    info.update(exit_code=result.returncode, log_sha256=digest(out / "build.log"))
    if result.returncode == 0:
        info.update(passed=True, binary_sha256=digest(out / "replay"))
    save(out / "build.json", info)
    result.check_returncode()


def weight_info(path, version):
    data = path.read_bytes()
    if version not in (1, 2) or len(data) < 24 or data[:4] != b"NBLB" or struct.unpack_from("<I4i", data, 4) != (version, 16, 89, 96, 28):
        raise ValueError("trained checkpoint geometry differs")
    if len(data) != 24 + 3681 * (4 if version == 1 else 2):
        raise ValueError("trained checkpoint length differs")
    if version == 1:
        values = struct.unpack("<3681f", data[24:])
    else:
        values = [struct.unpack("<f", struct.pack("<I", v << 16))[0]
                  for (v,) in struct.iter_unpack("<H", data[24:])]
    if not all(map(math.isfinite, values)) or any(values[r*96+c] != 0 for r in range(16) for c in range(90,96)):
        raise ValueError("nonfinite weight or nonzero input padding")
    return {"bytes": len(data), "sha256": digest(path)}


def run(args):
    protocol = json.loads(args.protocol.read_text())
    if protocol["script_sha256"] != digest(Path(__file__)) or protocol["learning_rates_1e6"] != [30, 300, 3000]:
        raise ValueError("training recipe differs from frozen protocol")
    build_dir = args.build.resolve()
    build_info = check_build(build_dir)
    if build_info["kind"] != "bitl-public-training-build":
        raise ValueError("requires the unchanged public training driver")
    converter = ENGINE / "training/bitl/tools/nblb.py"
    if digest(converter) != build_info["converter_sha256"]:
        raise ValueError("weight converter changed")
    initial = args.weights.resolve()
    if digest(initial) != BF16_SHA:
        raise ValueError("requires the shipped BF16 warm start")
    weight_info(initial, 2)
    fixtures, references = {}, {}
    # Both live/replay checks are a prerequisite, even though only the screen
    # trace supplies training targets or participates in candidate selection.
    for role in ("screen", "holdout"):
        checked = getattr(args, role + "_replay").resolve()
        reference = json.loads((checked / "report.json").read_text())
        if (not reference["passed"] or not reference["negative_control_rejected"]
                or reference["protocol_sha256"] != protocol["replay_protocol_sha256"]
                or reference["weights_sha256"] != BF16_SHA
                or reference["build_sha256"] != build_info["parent_build_sha256"]):
            raise ValueError("requires successful frozen baseline replay on both fixtures")
        directory = getattr(args, role + "_run").resolve() / "trial-0-0"
        info = trace_support.inspect_log(directory / "compress.log", directory)
        if info != reference["trace"]:
            raise ValueError("training trace changed after replay verification")
        meta = json.loads((directory.parent / "metadata.json").read_text())
        input_rows = [json.loads(line) for line in (directory.parent / "results.jsonl").read_text().splitlines()]
        if (len(input_rows) != 1 or input_rows[0]["input_sha256"] != protocol["fixture_input_sha256"][role]
                or meta["build"]["compiler"] != build_info["compiler"]):
            raise ValueError("training fixture identity or compiler differs")
        names = json.loads(re.findall(r'^CMIX_BITL_TRACE (\{[^\n]+\})$', (directory / "compress.log").read_text(), re.M)[0])
        fixtures[role] = {"trace": directory / names["trace"], "channel": directory / names["channel"], "bits": info["bits"]}
        references[role] = {"replay_report_sha256": digest(checked / "report.json"), "trace": info}
    out = new_output(args.output)
    shutil.copy2(args.protocol, out / "protocol.json")
    report = {**provenance("bitl-fixture-warm-start-screen"), "protocol_sha256": digest(args.protocol),
              "build_sha256": digest(build_dir / "build.json"), "binary_sha256": build_info["binary_sha256"],
              "initial_weights_sha256": BF16_SHA, "references": references, "runs": [], "candidates": [],
              "scope": "One offline CPU pass per fixed learning rate on screen only, same geometry. Frozen BF16 replay selects on screen, then checks one winner on disjoint fixture. Loss is rounded upstream diagnostic output, not archive bytes; no full-corpus or prize gain."}
    save(out / "report.json", report)
    clean_env = {k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_", "HUTTER_"))}

    def replay(label, role, weights, rate=None, target=None):
        data = fixtures[role]
        env = {"REPLAY_CHANNEL": str(data["channel"]), "REPLAY_LOAD": str(weights), "REPLAY_SEED": "1112363057"}
        if rate is None:
            env["REPLAY_FREEZE_AT"] = "1"
        else:
            env.update(REPLAY_LR1E6=str(rate), REPLAY_DUMP=str(target))
        command = [str(build_dir / "replay"), str(data["trace"]), "0", "0"]
        path = out / (label + ".log")
        started = time.monotonic()
        try:
            with path.open("wb") as log:
                result = subprocess.run(command, cwd=out, env={**clean_env, **env}, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=1200)
            status, code = "completed", result.returncode
        except subprocess.TimeoutExpired:
            status, code = "timeout", None
        record = {"label": label, "role": role, "command": command, "environment": env,
                  "wall_seconds": time.monotonic()-started, "status": status, "exit_code": code,
                  "log_sha256": digest(path)}
        report["runs"].append(record)
        save(out / "report.json", report)
        matches = re.findall(r'^bits=(\d+) cells=\d+ inputs=\d+ params=\d+ base_B=([\d.]+) head_B=([\d.]+)', path.read_text(), re.M)
        if code != 0 or len(matches) != 1 or int(matches[0][0]) != data["bits"]:
            raise ValueError("incomplete training/evaluation replay; saved " + label)
        record.update(bits=int(matches[0][0]), base_cost_bytes=float(matches[0][1]), head_cost_bytes=float(matches[0][2]))
        save(out / "report.json", report)
        return record

    baseline = replay("baseline-screen", "screen", initial)
    for rate in protocol["learning_rates_1e6"]:
        fp32, bf16 = out / f"lr{rate}-fp32.nblb", out / f"lr{rate}.nblb"
        train = replay(f"train-lr{rate}", "screen", initial, rate, fp32)
        full = weight_info(fp32, 1)
        command = [sys.executable, str(converter), "v2", str(fp32), str(bf16)]
        with (out / f"export-lr{rate}.log").open("wb") as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        compact = weight_info(bf16, 2)
        evaluation = replay(f"evaluate-lr{rate}-screen", "screen", bf16)
        candidate = {"learning_rate_1e6": rate, "fp32": full, "bf16": compact,
                     "converter_command": command, "export_log_sha256": digest(out / f"export-lr{rate}.log"),
                     "screen_cost_bytes": evaluation["head_cost_bytes"],
                     "screen_delta_bytes": evaluation["head_cost_bytes"] - baseline["head_cost_bytes"]}
        report["candidates"].append(candidate)
        save(out / "report.json", report)
    winner = min(report["candidates"], key=lambda r: (r["screen_cost_bytes"], r["learning_rate_1e6"]))
    report["selected_before_holdout"] = dict(winner)
    # Save the selected model hash before ever evaluating a candidate on holdout.
    save(out / "selection.json", report["selected_before_holdout"])
    report["selection_sha256"] = digest(out / "selection.json")
    report["screen_gate_passed"] = winner["screen_delta_bytes"] <= -1.0 and winner["bf16"]["sha256"] != BF16_SHA
    if report["screen_gate_passed"]:
        holdout_baseline = replay("baseline-holdout", "holdout", initial)
        holdout = replay("selected-holdout", "holdout", out / f"lr{winner['learning_rate_1e6']}.nblb")
        report["holdout_delta_bytes"] = holdout["head_cost_bytes"] - holdout_baseline["head_cost_bytes"]
        report["holdout_gate_passed"] = report["holdout_delta_bytes"] <= -1.0
    else:
        report["holdout_gate_passed"] = False
    report["eligible_for_archive_trial"] = report["screen_gate_passed"] and report["holdout_gate_passed"]
    report["passed"] = True  # Completed protocol, even when every model is rejected.
    save(out / "report.json", report)
    print(json.dumps({k:report[k] for k in ("passed", "screen_gate_passed", "holdout_gate_passed", "eligible_for_archive_trial")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compiler = sub.add_parser("build")
    for key in ("replay-build", "output"):
        compiler.add_argument("--" + key, type=Path, required=True)
    experiment = sub.add_parser("run")
    for key in ("build", "protocol", "weights", "screen-replay", "holdout-replay", "screen-run", "holdout-run", "output"):
        experiment.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    try:
        return build(args) if args.command == "build" else run(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
