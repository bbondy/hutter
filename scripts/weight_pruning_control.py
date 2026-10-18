#!/usr/bin/env python3
"""Check removed-neuron kernels against an independently masked full-width model."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess

from benchmark import capture, measured
from competitive import differences, inventory
from make_samples import digest
from weight_kernel_probe import SOURCES
from weight_permutation import ENGINE, MANIFEST, ROOT, check_tensors, upstream, wc

PROBE = ROOT / "scripts/probes/weight_pruning_control.cpp"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("build", "containers", "protocol", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    parent = args.containers / "report.json"
    if digest(parent) != protocol["container_report_sha256"]:
        raise ValueError("container results differ from frozen control")
    frozen = json.loads(MANIFEST.read_text())
    if any(differences(frozen["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream differs")
    original = ENGINE / protocol["weights_file"]
    if digest(original) != protocol["weights_sha256"]:
        raise ValueError("original model differs")
    candidates = json.loads(parent.read_text())["variants"]
    if list(candidates) != protocol["variants"]:
        raise ValueError("candidate list differs")
    build = args.build.resolve()
    source = build / "source"
    meta = json.loads((build / "build.json").read_text())
    for name, info in meta["source_files"].items():
        if digest(source / name) != info["sha256"]:
            raise ValueError("recorded source differs: " + name)
    compiler = shlex.split(next(part[3:] for part in meta["command"] if part.startswith("CC=")))
    if capture(compiler[0], "--version") != meta["compiler"]:
        raise ValueError("compiler differs")
    if meta.get("simde_commit"):
        simde = build / "simde"
        if (capture("git", "-C", str(simde), "rev-parse", "HEAD") != meta["simde_commit"]
                or capture("git", "-C", str(simde), "status", "--porcelain")):
            raise ValueError("SIMDe differs")
    output = args.output.resolve()
    if output.is_relative_to(ENGINE) or output.is_relative_to(source):
        raise ValueError("output must be outside source trees")
    output.mkdir(parents=True, exist_ok=False)
    makefile = (source / "makefile").read_text()

    def variable(name):
        match = re.search(r"^" + name + r"\s*:=\s*(.*)$", makefile, re.M)
        if match is None or "$" in match[1]:
            raise ValueError("expected literal compiler setting " + name)
        return shlex.split(match[1])

    flags, cold = variable("TF1_CXXFLAGS"), set(variable("TF1_SRCS_OZ"))
    commands, objects = [], []
    for name in SOURCES:
        path, obj = "src/" + name, output / (Path(name).stem + ".o")
        commands.append(compiler + flags + (variable("TF1_OZ_FLAGS") if path in cold else [])
                        + ["-c", path, "-o", str(obj)])
        objects.append(str(obj))
    binary = output / "probe"
    commands.append(compiler + flags + (["-no-pie"] if "-fno-pie" in flags else [])
                    + ["-I" + str(source / "src"), str(PROBE), *objects, "-o", str(binary)])
    report = {"kind": "pruning-masked-width-control", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)), "probe_source_sha256": digest(PROBE),
              "protocol_sha256": digest(args.protocol), "container_report_sha256": digest(parent),
              "build_metadata_sha256": digest(build / "build.json"), "compiler": meta["compiler"],
              "platform": meta["platform"], "commands": commands, "results": {}, "passed": False,
              "scope": "Synthetic kernel checks of zeroed versus removed neurons. No equivalence to the original unmasked model, full-transformer check, Linux result or prize score is implied."}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    with (output / "build.log").open("wb") as log:
        for command in commands:
            subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
    report["binary_sha256"] = digest(binary)
    _, entries = upstream.read_container(str(original))
    arrays = {name: array for name, _, array in entries}
    for variant, record in candidates.items():
        candidate = args.containers / (variant + ".c4")
        removed_file = args.containers / (variant + "-removed.json")
        if (digest(candidate) != record["container_sha256"]
                or digest(removed_file) != record["removed_indices_sha256"]):
            raise ValueError("candidate or removal map changed")
        removed = {int(k): v for k, v in json.loads(removed_file.read_text()).items()}
        # Independently construct masked controls: retain all shapes, scales and
        # down columns; only replace the removed neurons' up-weight rows by zero.
        changed, mapping = {}, []
        if set(removed) != set(range(16)):
            raise ValueError("incomplete layer map")
        for layer in range(16):
            name = f"blocks.{layer}.mlp.up.weight.q"
            width = arrays[name].shape[0]
            drop = removed[layer]
            if drop != sorted(set(drop)) or not drop or min(drop) < 0 or max(drop) >= width:
                raise ValueError("invalid removal indices")
            keep = [i for i in range(width) if i not in set(drop)]
            changed[name] = arrays[name].copy()
            changed[name][drop, :] = 0
            mapping.append(" ".join(map(str, [width, len(keep), *keep])))
        masked_entries = [(n, c, changed.get(n, a)) for n, c, a in entries]
        masked = output / (variant + "-masked.c4")
        wc.write_tensor_file_v4(str(masked), masked_entries)
        check_tensors(masked_entries, wc.read_tensor_file_v3(str(masked)))
        expected, _, _ = upstream.prune(entries, removed)
        check_tensors(expected, wc.read_tensor_file_v3(str(candidate)))
        mapfile = output / (variant + "-keep.txt")
        mapfile.write_text("\n".join(mapping) + "\n")
        result = {"masked_sha256": digest(masked), "candidate_sha256": digest(candidate),
                  "map_sha256": digest(mapfile), "checks": {}}
        for label, first in (("masked", masked), ("negative_unmasked", original)):
            logfile = output / (variant + "-" + label + ".log")
            run = measured([str(binary), str(first.resolve()), str(candidate.resolve()), str(mapfile)], logfile, 300)
            summaries = [json.loads(line) for line in logfile.read_text().splitlines() if line.startswith('{"passed"')]
            passed = run["status"] == "ok" and len(summaries) == 1 and summaries[0]["passed"]
            # A crash or timeout is not evidence that the negative control works.
            rejected = run.get("exit_code") in (4, 5, 6, 7) and not summaries
            result["checks"][label] = {"execution": run, "log_sha256": digest(logfile),
                                       "summary": summaries[0] if summaries else None,
                                       "expected_outcome": bool(passed if label == "masked" else rejected)}
        result["passed"] = all(c["expected_outcome"] for c in result["checks"].values())
        report["results"][variant] = result
        save()
        print(variant, "PASS" if result["passed"] else "FAIL", flush=True)
    report["passed"] = all(result["passed"] for result in report["results"].values())
    save()
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
