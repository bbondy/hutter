#!/usr/bin/env python3
"""Recreate neuron permutations, check x86 kernels, and compare full fixtures."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from benchmark import capture
from make_samples import digest
from replay_fixture import replay
from weight_equivalence import verify

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=("screen", "holdout"))
    parser.add_argument("--enwik8", required=True, type=Path)
    args = parser.parse_args()
    work = ROOT / "build" / ("linux-weights-" + args.role)
    evidence = ROOT / "build/weight-evidence" / args.role
    work.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    host = {"cpu": capture("lscpu"), "kernel": capture("uname", "-a"),
            "commit": capture("git", "rev-parse", "HEAD"), "python": sys.version}
    (evidence / "host.json").write_text(json.dumps(host, indent=2) + "\n")

    def run(*command):
        print("Running", " ".join(map(str, command)), flush=True)
        subprocess.run([sys.executable, *map(str, command)], cwd=ROOT, check=True)

    builds, runs = [], []
    try:
        containers = work / "containers"
        run("scripts/weight_permutation.py", "--protocol",
            "benchmarks/weights/20261017-permutation-protocol-v1/protocol.json", "--output", containers)
        frozen = ROOT / "benchmarks/weights/20261017-archive-protocol-v1/protocol.json"
        protocol = json.loads(frozen.read_text())
        candidate = containers / "mlp-scale.c4"
        if digest(candidate) != protocol["candidate_container_sha256"]:
            raise ValueError("Linux container differs from frozen Mac candidate")
        base = work / "build-baseline"
        builds.append(base)
        run("scripts/linux_cmix.py", "build", "--output", base, "--jobs", "2")
        source_manifest = ROOT / "benchmarks/article-order/20261017-projection-protocol-v2" / (args.role + ".json")
        manifest = replay(source_manifest, args.enwik8, base, work / "fixture")
        protocol["parent_protocol_sha256"] = digest(frozen)
        protocol["fixtures"][args.role]["manifest_sha256"] = digest(manifest)
        protocol_path = work / "protocol.json"
        protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
        run("scripts/weight_kernel_probe.py", "--build", base, "--original",
            "engines/cmix-neif/weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4",
            "--candidates", *(containers / (name + ".c4") for name in
                               ("mlp-scale", "mlp-zero-count", "mlp-row-mean")),
            "--output", work / "kernels")
        changed = work / "build-candidate"
        builds.append(changed)
        run("scripts/linux_cmix.py", "build", "--weight-container", candidate,
            "--output", changed, "--jobs", "2")
        for name, build in (("baseline", base), ("candidate", changed)):
            trial = work / ("run-" + name)
            runs.append(trial)
            run("scripts/linux_cmix.py", "bench", work / "fixture/upstream.ready", "--build", build,
                "--manifest", manifest, "--output", trial, "--timeout", "2400")
        status = verify(SimpleNamespace(protocol=protocol_path, manifest=manifest, build=base,
                                        baseline=runs[0], candidate=runs[1], role=args.role,
                                        output=evidence / "comparison"))
        if status:
            raise ValueError("weight permutation changed fixture archive or context")
    finally:
        for directory in ("containers", "fixture", "kernels"):
            source = work / directory
            if source.exists():
                target = evidence / directory
                target.mkdir()
                for path in source.iterdir():
                    if path.is_file() and path.suffix in (".json", ".log", ".c4", ".ready", ".xml"):
                        shutil.copyfile(path, target / path.name)
        if (work / "protocol.json").exists():
            shutil.copyfile(work / "protocol.json", evidence / "protocol.json")
        for build in builds:
            target = evidence / build.name
            target.mkdir()
            for name in ("build.json", "build.log", "prepare-build.log"):
                if (build / name).exists():
                    shutil.copyfile(build / name, target / name)
        for run_dir in runs:
            if not run_dir.exists():
                continue
            target = evidence / run_dir.name
            target.mkdir()
            for name in ("metadata.json", "results.jsonl", "cmix"):
                if (run_dir / name).exists():
                    shutil.copyfile(run_dir / name, target / name)
            for name in ("compress.log", "decompress.log", "payload.cmix", "restored"):
                path = run_dir / "trial-0-0" / name
                if path.exists():
                    shutil.copyfile(path, target / name)


if __name__ == "__main__":
    main()
