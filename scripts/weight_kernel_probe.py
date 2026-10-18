#!/usr/bin/env python3
"""Compile a weight-permutation check against a recorded build's actual kernels."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

from benchmark import capture, measured
from competitive import ENGINE
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/probes/weight_permutation.cpp"
SOURCES = ("tf1/weights_io.cpp", "tf1/weights_io_compressed.cpp", "tf1/kernels.cpp",
           "tf1/opt/arena_build.cpp", "tf1/opt/glue.cpp", "tf1/opt/qmat_dense.cpp",
           "tf1/opt/qmat_sparse.cpp")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("build", "original", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    source = build / "source"
    meta = json.loads((build / "build.json").read_text())
    for name, info in meta["source_files"].items():
        if digest(source / name) != info["sha256"]:
            raise ValueError("recorded build source changed: " + name)
    output = args.output.resolve()
    if output.is_relative_to(ENGINE) or output.is_relative_to(source):
        raise ValueError("probe output must be outside the source trees")
    output.mkdir(parents=True, exist_ok=False)
    makefile = (source / "makefile").read_text()

    def variable(name):
        match = re.search(r"^" + name + r"\s*:=\s*(.*)$", makefile, re.M)
        if match is None or "$" in match[1]:
            raise ValueError("expected literal compiler setting " + name)
        return shlex.split(match[1])

    cc = next(part[3:] for part in meta["command"] if part.startswith("CC="))
    compiler = shlex.split(cc)
    if capture(compiler[0], "--version") != meta["compiler"]:
        raise ValueError("compiler differs from the recorded build")
    if meta.get("simde_commit"):
        simde = build / "simde"
        if (capture("git", "-C", str(simde), "rev-parse", "HEAD") != meta["simde_commit"]
                or capture("git", "-C", str(simde), "status", "--porcelain")):
            raise ValueError("SIMDe source differs from the recorded build")
    flags = variable("TF1_CXXFLAGS")
    cold = set(variable("TF1_SRCS_OZ"))
    commands, objects = [], []
    for name in SOURCES:
        path = "src/" + name
        obj = output / (Path(name).stem + ".o")
        command = compiler + flags + (variable("TF1_OZ_FLAGS") if path in cold else [])
        commands.append(command + ["-c", path, "-o", str(obj)])
        objects.append(str(obj))
    binary = output / "probe"
    link_flags = ["-no-pie"] if "-fno-pie" in flags else []
    commands.append(compiler + flags + link_flags + ["-I" + str(source / "src"), str(PROBE), *objects,
                                        "-o", str(binary)])
    report = {"kind": "weight-permutation-kernel-check", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)), "probe_source_sha256": digest(PROBE),
              "build_metadata_sha256": digest(build / "build.json"),
              "compiler": meta["compiler"], "platform": meta["platform"],
              "commands": commands, "original_sha256": digest(args.original), "results": {},
              "scope": "Synthetic MLP block tests using recorded source and per-file flags; not a full coder or prize result."}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    with (output / "build.log").open("wb") as log:
        for command in commands:
            subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
    report["binary_sha256"] = digest(binary)
    save()
    for i, candidate in enumerate(args.candidates):
        log = output / f"candidate-{i}.log"
        run = measured([str(binary), str(args.original.resolve()), str(candidate.resolve())], log, 300)
        summaries = [json.loads(line) for line in log.read_text().splitlines() if line.startswith('{"passed"')]
        passed = run["status"] == "ok" and len(summaries) == 1 and summaries[0]["passed"]
        report["results"][candidate.name] = {"candidate_sha256": digest(candidate), "passed": passed,
                                            "execution": run, "log_sha256": digest(log),
                                            "summary": summaries[0] if summaries else None}
        save()
        print(candidate.name, "PASS" if passed else "FAIL", flush=True)
    return int(not all(result["passed"] for result in report["results"].values()))


if __name__ == "__main__":
    sys.exit(main())
