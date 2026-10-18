#!/usr/bin/env python3
"""Run a declared model experiment on one frozen fixture and Linux CI host."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from benchmark import capture
from make_samples import digest
from model_history import summarize
from replay_fixture import replay

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = {
    "link-context": "20261017-protocol-v2",
    "adaptive-depth": "20261017-depth-protocol-v1",
    "exact-target": "20261017-retrieval-protocol-v1",
    "exact-target-confirmation": "20261017-retrieval-confirmation-protocol-v1",
    "bitl-trace": "20261017-bitl-trace-protocol-v2",
    "bitl-warm-start": "20261017-bitl-archive-protocol-v1",
    "bitl-broad": "20261018-bit-weight-broad-protocol-v1",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("screen", "holdout", "confirmation"), required=True)
    parser.add_argument("--enwik8", type=Path, required=True)
    parser.add_argument("--experiment", choices=EXPERIMENTS, default="link-context")
    args = parser.parse_args()
    group = "training" if args.experiment in ("bitl-trace", "bitl-warm-start", "bitl-broad") else "model-variants"
    original_protocol = ROOT / "benchmarks" / group / EXPERIMENTS[args.experiment] / "protocol.json"
    frozen_protocol = json.loads(original_protocol.read_text())
    if args.role not in frozen_protocol["fixtures"]:
        raise ValueError("fixture role is not declared by this experiment")
    models = tuple(frozen_protocol["variants"])
    if not models or models[0] != "baseline":
        raise ValueError("frozen experiment must start with its baseline")
    work = ROOT / "build" / ("linux-ci-" + args.experiment + "-" + args.role)
    evidence = ROOT / "build/linux-evidence" / args.role
    work.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    host = {"lscpu": capture("lscpu"), "kernel": capture("uname", "-a"),
            "memory": Path("/proc/meminfo").read_text(), "disk": capture("df", "-h", str(work)),
            "commit": capture("git", "rev-parse", "HEAD")}
    (evidence / "host.json").write_text(json.dumps(host, indent=2) + "\n")
    builds, runs = [], []
    manifest = protocol_path = None
    try:
        for name in models:
            build = work / ("build-" + name)
            builds.append(build)
            variant_args = {"retrieval-exact-target": ["--retrieval-variant", "exact-target"],
                            "bit-trace-fixture": ["--bit-trace-variant", "fixture"],
                            "bit-weight-warm-start-lr3000-v1": ["--bit-weight-variant", "warm-start-lr3000-v1"]}.get(name, ["--variant", name])
            subprocess.run([sys.executable, "scripts/linux_cmix.py", "build", *variant_args,
                            "--output", str(build), "--jobs", "2"], cwd=ROOT, check=True)
            if manifest is None:
                source_manifest = ROOT / frozen_protocol["fixtures"][args.role]["manifest_path"]
                if digest(source_manifest) != frozen_protocol["fixtures"][args.role]["manifest_sha256"]:
                    raise ValueError("fixture manifest differs from frozen protocol")
                manifest = replay(source_manifest, args.enwik8, build, work / "fixture")
                protocol = frozen_protocol
                protocol["parent_protocol_sha256"] = digest(original_protocol)
                protocol["platform_scope"] = "Native Linux x86-64, all models serial on one CI host; not a full prize run"
                protocol["fixtures"][args.role]["manifest_sha256"] = digest(manifest)
                tree = ast.parse((ROOT / "scripts/native_cmix.py").read_text())
                bench = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "bench")
                protocol["runner_control"] = {
                    "bench_function_ast_sha256": hashlib.sha256(ast.dump(bench).encode()).hexdigest(),
                    "commit": host["commit"], "changes": "Shared benchmark now records Linux CPU identity; same round-trip procedure."
                }
                protocol_path = work / "protocol.json"
                protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
                shutil.copyfile(protocol_path, evidence / "protocol.json")
                shutil.copyfile(manifest, evidence / "manifest.json")
            run = work / ("run-" + name)
            runs.append(run)
            subprocess.run([sys.executable, "scripts/linux_cmix.py", "bench", str(work / "fixture/upstream.ready"),
                            "--build", str(build), "--manifest", str(manifest), "--output", str(run),
                            "--timeout", "7200" if args.experiment == "bitl-broad" else "1800"], cwd=ROOT, check=True)
        summarize(SimpleNamespace(manifest=manifest, protocol=protocol_path, role=args.role,
                                  build=builds[0], runs=runs, output=evidence / "comparison"))
        if args.experiment == "bitl-trace":
            audit, replay_build, verification = work / "weight-audit", work / "replay-build", work / "replay-verification"
            replay_protocol = ROOT / "benchmarks/training/20261017-bitl-replay-protocol-v3/protocol.json"
            adapted = json.loads(replay_protocol.read_text())
            adapted["parent_protocol_sha256"] = digest(replay_protocol)
            adapted["trace_protocol_sha256"] = digest(protocol_path)
            adapted["platform_scope"] = "Native Linux fixture tracing and frozen replay; not a full release result."
            adapted_path = work / "replay-protocol.json"
            adapted_path.write_text(json.dumps(adapted, indent=2) + "\n")
            subprocess.run([sys.executable, "scripts/bitl_weight_audit.py", "--output", str(audit)], check=True, cwd=ROOT)
            subprocess.run([sys.executable, "scripts/bitl_replay.py", "build", "--native-build", str(builds[-1]),
                            "--output", str(replay_build)], check=True, cwd=ROOT)
            subprocess.run([sys.executable, "scripts/bitl_replay.py", "verify", "--build", str(replay_build),
                            "--run", str(runs[-1]), "--comparison", str(evidence / "comparison"),
                            "--weights", str(audit / "F2L.nblb"), "--protocol", str(adapted_path),
                            "--output", str(verification)], check=True, cwd=ROOT)
    finally:
        # Keep partial evidence even after a compile, timeout or round-trip failure.
        if (work / "fixture").exists():
            shutil.copytree(work / "fixture", evidence / "fixture")
        for build in builds:
            dest = evidence / build.name
            dest.mkdir()
            for name in ("build.json", "build.log", "prepare-build.log"):
                if (build / name).exists():
                    shutil.copyfile(build / name, dest / name)
        for run in runs:
            if not run.exists():
                continue
            dest = evidence / run.name
            dest.mkdir()
            for name in ("metadata.json", "results.jsonl", "cmix"):
                if (run / name).exists():
                    shutil.copyfile(run / name, dest / name)
            trial = run / "trial-0-0"
            for name in ("compress.log", "decompress.log", "payload.cmix", "restored"):
                if (trial / name).exists():
                    shutil.copyfile(trial / name, dest / name)
        # Keep bounded replay evidence on success or failure. Raw traces remain
        # on the temporary runner; their independently checked hashes are saved.
        if args.experiment == "bitl-trace":
            for name in ("weight-audit", "replay-build", "replay-verification"):
                source = work / name
                if source.is_dir():
                    dest = evidence / name
                    dest.mkdir()
                    for file in source.iterdir():
                        if file.is_file() and file.suffix in (".json", ".log"):
                            shutil.copy2(file, dest / file.name)


if __name__ == "__main__":
    main()
