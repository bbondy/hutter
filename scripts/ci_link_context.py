#!/usr/bin/env python3
"""Run one frozen fixture's model comparisons on a single Linux CI host."""
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
MODELS = ("baseline", "z3-budget128", "z3-chunk32", "z3-off")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("screen", "holdout"), required=True)
    parser.add_argument("--enwik8", type=Path, required=True)
    args = parser.parse_args()
    work = ROOT / "build" / ("linux-ci-" + args.role)
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
        for name in MODELS:
            build = work / ("build-" + name)
            builds.append(build)
            subprocess.run([sys.executable, "scripts/linux_cmix.py", "build", "--variant", name,
                            "--output", str(build), "--jobs", "2"], cwd=ROOT, check=True)
            if manifest is None:
                source_manifest = ROOT / "benchmarks/article-order/20261017-projection-protocol-v1" / (args.role + ".json")
                manifest = replay(source_manifest, args.enwik8, build, work / "fixture")
                original_protocol = ROOT / "benchmarks/model-variants/20261017-protocol-v1/protocol.json"
                protocol = json.loads(original_protocol.read_text())
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
                            "--timeout", "1800"], cwd=ROOT, check=True)
        summarize(SimpleNamespace(manifest=manifest, protocol=protocol_path, role=args.role,
                                  build=builds[0], runs=runs, output=evidence / "comparison"))
    finally:
        # Keep partial evidence even after a compile, timeout or round-trip failure.
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


if __name__ == "__main__":
    main()
