#!/usr/bin/env python3
"""Verify, inspect, or build the competitive engine without modifying its source."""
import argparse
import datetime
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time

from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engines/cmix-neif"
MANIFEST = ROOT / "engines/cmix-neif.upstream.json"
TOOLS = "bash make clang++-18 clang-18 ld.lld-18 llvm-profdata-18 llvm-strip-18 llvm-objcopy-18 objcopy gawk python3 gcc tar".split()


def inventory(source):
    return {str(p.relative_to(source)): {"sha256": digest(p), "executable": bool(p.stat().st_mode & 0o111)}
            for p in sorted(source.rglob("*")) if p.is_file()}


def differences(expected, actual):
    return {"changed": sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k]),
            "missing": sorted(expected.keys() - actual.keys()),
            "added": sorted(actual.keys() - expected.keys())}


def capture(command):
    result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=15)
    return result.stdout.strip()


def problems():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        return [f"Requires Linux x86-64; this host is {platform.system()} {platform.machine()}."]
    errors = [f"Missing build tool: {tool}" for tool in TOOLS if not shutil.which(tool)]
    cpuinfo = Path("/proc/cpuinfo").read_text().lower()
    flag_lines = [set(line.split(":", 1)[1].split()) for line in cpuinfo.splitlines() if line.startswith("flags")]
    required = {"avx2", "fma", "f16c", "bmi1", "bmi2", "movbe", "xsave"}
    if not flag_lines or any(not required <= flags or not ({"abm", "lzcnt"} & flags) for flags in flag_lines):
        errors.append("CPU flags do not establish the required x86-64-v3 support (including AVX2/FMA).")
    if shutil.which("clang-18"):
        runtime = capture(["clang-18", "--print-file-name=libclang_rt.profile-x86_64.a"])
        if not Path(runtime).is_file():
            errors.append("Missing compiler-rt profiling runtime libclang_rt.profile-x86_64.a.")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "doctor", "build"))
    parser.add_argument("--output", type=Path, default=ROOT / "build/competitive/cmix-neif")
    args = parser.parse_args()
    upstream = json.loads(MANIFEST.read_text())
    files = inventory(ENGINE)
    delta = differences(upstream["files"], files)
    print(f"Engine: {upstream['name']}; upstream commit {upstream['commit']}")
    print(f"Source: {len(files)} files; {sum(map(len, delta.values()))} differences from pinned upstream")
    if args.command == "verify":
        if any(delta.values()):
            print(json.dumps(delta, indent=2))
            return 1
        print("All file contents and executable bits match the upstream manifest.")
        return 0
    errors = problems()
    if errors:
        for error in errors:
            print(error)
        print("See engines/README.md. No installation or build was attempted.")
        return 1
    print("Required platform, CPU flags and build tools are present.")
    print("This check does not prove memory/time eligibility or exact Ubuntu package versions.")
    if args.command == "doctor":
        return 0
    destination = args.output.resolve()
    if destination.is_relative_to(ENGINE):
        parser.error("build output must be outside the vendored source directory")
    destination.mkdir(parents=True, exist_ok=False)
    # build.sh works in its caller's directory and removes only its .build copy.
    # A new output directory prevents its cleanup from affecting earlier work.
    command = ["bash", str(ENGINE / "build.sh")]
    metadata = {"date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "repo_commit": capture(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
                "upstream_commit": upstream["commit"], "source_changes": delta,
                "platform": platform.platform(), "machine": platform.machine(),
                "command": command, "working_directory": str(destination),
                "tools": {tool: shutil.which(tool) for tool in TOOLS},
                "compiler_version": capture(["clang++-18", "--version"]),
                "linker_version": capture(["ld.lld-18", "--version"])}
    if shutil.which("dpkg-query"):
        metadata["packages"] = capture(["dpkg-query", "-W", "-f=${Package}=${Version}\n"])
    (destination / "source-files.json").write_text(json.dumps(files, indent=2) + "\n")
    (destination / "build.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Building; output goes to {destination / 'build.log'}", flush=True)
    start = time.monotonic()
    with (destination / "build.log").open("wb") as log:
        result = subprocess.run(command, cwd=destination, stdout=log, stderr=subprocess.STDOUT)
    metadata.update(exit_code=result.returncode, wall_seconds=time.monotonic() - start)
    binary = destination / "comp9"
    if result.returncode == 0 and binary.is_file():
        metadata.update(binary_sha256=digest(binary), binary_bytes=binary.stat().st_size)
        metadata["matches_upstream_binary"] = metadata["binary_sha256"] == upstream["expected_comp9_sha256"]
    (destination / "build.json").write_text(json.dumps(metadata, indent=2) + "\n")
    if result.returncode or not binary.is_file():
        print("Build failed; inspect build.log and build.json.")
        return 1
    print(f"Built {binary}; exact upstream binary match: {metadata['matches_upstream_binary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
