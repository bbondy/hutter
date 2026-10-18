#!/usr/bin/env python3
"""Rebuild upstream's non-inference training-row dumper from a verified stream build.

This produces training/diagnostic data, not a decodable compressed archive.
It does not run GPU training or allocate the much larger PPMd-prior raster.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from benchmark import capture, measured
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
from native_cmix import PORT, SIMDE_COMMIT
from native_stream import EXPECTED
import training_read_cache

ROOT = Path(__file__).resolve().parents[1]
DUMP = (7117383324, "58fc6c74c09400192c28cf3608e6eeb0387ba4f40b4255d39dbc8ac5e0bf66a0")


def run(args):
    upstream = json.loads(MANIFEST.read_text())
    if any(differences(upstream["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream differs")
    parent = args.stream_build.resolve()
    preparation = json.loads((parent / "report.json").read_text())
    if preparation["kind"] != "native-full-coder-stream" or not preparation["passed"]:
        raise ValueError("requires a successful full-stream preparation build")
    if preparation["upstream_commit"] != upstream["commit"] or preparation["platform"] != platform.platform():
        raise ValueError("stream build belongs to a different platform or upstream revision")
    for name, (size, sha) in EXPECTED.items():
        file = parent / "run" / name
        if file.stat().st_size != size or digest(file) != sha:
            raise ValueError("prepared full stream differs: " + name)
    source_files = preparation["source_files"]
    for name, expected in source_files.items():
        file = parent / "source" / name
        if digest(file) != expected["sha256"] or bool(file.stat().st_mode & 0o111) != expected["executable"]:
            raise ValueError("training source differs from preparation record: " + name)
    darwin = platform.system() == "Darwin"
    simde = parent / "simde"
    if darwin and (capture("git", "-C", str(simde), "rev-parse", "HEAD") != SIMDE_COMMIT
                   or capture("git", "-C", str(simde), "status", "--porcelain")):
        raise ValueError("SIMDe source differs")
    output = args.output.resolve()
    if output.is_relative_to(ENGINE) or output.is_relative_to(PORT) or output.is_relative_to(parent):
        raise ValueError("output must be outside source and prior build trees")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < 15 * 1024**3:
        raise ValueError("requires 15 GiB free for the full row dump and diagnostics")
    output.mkdir(exist_ok=False)
    source = output / "source"
    source.mkdir()
    for name in source_files:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parent / "source" / name, target)
    if inventory(source) != source_files:
        raise ValueError("copied training sources differ")
    if darwin:
        (output / "simde").symlink_to(simde.resolve(), target_is_directory=True)
    compiler = "clang++" if darwin else "clang++-18"
    command = ["make", f"-j{args.jobs}", "CC=" + compiler + " -DTRAIN_MODE=2" +
               (" -Isrc -I../simde" if darwin else ""), "cmix"]
    protocol = args.protocol.resolve()
    frozen = json.loads(protocol.read_text())
    if frozen["expected_dump"] != {"bytes": DUMP[0], "sha256": DUMP[1]}:
        raise ValueError("frozen dump reference differs from upstream")
    if frozen["training_patch_sha256"] != preparation["training_patch_sha256"]:
        raise ValueError("training patch differs from protocol")
    cache = None
    if args.read_cache:
        if frozen.get("read_cache_recipe_sha256") != digest(Path(training_read_cache.__file__)):
            raise ValueError("read-cache recipe differs from frozen protocol")
        cache = training_read_cache.apply(source)
    elif frozen.get("read_cache_recipe_sha256"):
        raise ValueError("protocol requires the diagnostic read cache")
    shutil.copyfile(protocol, output / "protocol.json")
    report = {"kind": "upstream-training-row-dump-reproduction", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)), "protocol_sha256": digest(protocol),
              "parent_preparation_report_sha256": digest(parent / "report.json"),
              "upstream_commit": upstream["commit"], "platform": platform.platform(),
              "compiler": capture(compiler, "--version"), "build_command": command,
              "source_files": inventory(source), "simde_commit": SIMDE_COMMIT if darwin else None,
              "read_cache": cache,
              "scope": "TRAIN_MODE=2 diagnostic/training rows; constant predictions, no transformer forward pass, no decodable archive or prize score. Concurrent timing is exploratory.",
              "passed": False}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    with (output / "build.log").open("wb") as log:
        result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
    report["build_exit_code"] = result.returncode
    save()
    result.check_returncode()
    binary = source / "cmix"
    report["binary_sha256"] = digest(binary)
    work = output / "run"
    work.mkdir()
    shutil.copyfile(ENGINE / "dictionary/english.dic", work / ".dict")
    report["dictionary_sha256"] = digest(work / ".dict")
    (work / "aus").symlink_to("/dev/null")
    command = [str(binary), "-n", str(parent / "run/archive.cmix.temp.vorpack"), "./aus"]
    save()  # Preserve binary and asset identity while a long dump is still running.
    previous = Path.cwd()
    try:
        os.chdir(work)
        report["execution"] = measured(command, output / "dump.log", args.timeout)
    finally:
        os.chdir(previous)
    report["outputs"] = {}
    for name in ("paket-zeilen.bin", "zonenmaske.u8", "match-bytes.uint8", "match-len.uint8"):
        file = work / name
        if file.is_file():
            report["outputs"][name] = {"bytes": file.stat().st_size, "sha256": digest(file)}
    report["matches_upstream_dump"] = report["outputs"].get("paket-zeilen.bin") == frozen["expected_dump"]
    report["raster_lengths_match"] = all(report["outputs"].get(name, {}).get("bytes") == 552750204
                                        for name in ("zonenmaske.u8", "match-bytes.uint8", "match-len.uint8"))
    report["log_sha256"] = digest(output / "dump.log")
    report["coded_stream_count_matches"] = "coded stream bytes 552750204" in (output / "dump.log").read_text(errors="replace")
    report["passed"] = (report["execution"]["status"] == "ok" and report["matches_upstream_dump"]
                        and report["raster_lengths_match"] and report["coded_stream_count_matches"])
    save()
    print(json.dumps({key: report[key] for key in ("passed", "matches_upstream_dump", "outputs")}, indent=2))
    return int(not report["passed"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stream-build", "protocol", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--read-cache", action="store_true", help="requires a separately frozen read-cache protocol")
    args = parser.parse_args()
    if (platform.system(), platform.machine()) not in (("Darwin", "arm64"), ("Linux", "x86_64")):
        parser.error("requires native Apple Silicon or Linux x86-64")
    if args.jobs < 1 or args.timeout <= 0:
        parser.error("jobs and timeout must be positive")
    try:
        return run(args)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
