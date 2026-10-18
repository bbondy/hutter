#!/usr/bin/env python3
"""Compare bounded output prefixes from real release binaries on full enwik9.

These intentionally stopped encodings are neither complete archives nor round
trips. They exercise the real package, dictionary derivation and full-input
preprocessing before comparing emitted coder bytes. No prize score is inferred.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import time

from benchmark import capture
from make_samples import digest
from package_structure import inspect


def rss_tree(pid):
    """Sample current RSS of the process and its live descendants, in bytes."""
    seen, pending, total = set(), [pid], 0
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            status = Path(f"/proc/{current}/status").read_text()
            total += next((int(line.split()[1]) * 1024 for line in status.splitlines()
                           if line.startswith("VmRSS:")), 0)
            children = Path(f"/proc/{current}/task/{current}/children").read_text()
            pending.extend(int(child) for child in children.split())
        except (OSError, ValueError):
            pass  # Processes can exit between the two reads.
    return total


def capture_prefix(command, work, target, count, timeout, required_marker=None, post_marker_margin=0):
    """Run one owned process group, snapshot its prefix, always terminate it."""
    started = time.monotonic()
    result = {"command": command, "complete_archive": False,
              "sampled_process_tree_peak_rss_bytes": 0, "status": "running"}
    with (work / "run.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=work, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, env={**os.environ, "LC_ALL": "C"})
        try:
            while True:
                result["sampled_process_tree_peak_rss_bytes"] = max(
                    result["sampled_process_tree_peak_rss_bytes"], rss_tree(process.pid))
                if required_marker and "required_phase_observed" not in result:
                    if required_marker in (work / "run.log").read_text(errors="replace"):
                        result["required_phase_observed"] = {
                            "marker": required_marker,
                            "output_bytes_when_observed": target.stat().st_size if target.exists() else 0,
                            "wall_seconds": time.monotonic() - started}
                if process.poll() is not None:
                    result["status"] = "exited_before_capture"
                    break
                if target.exists() and target.stat().st_size >= count:
                    if required_marker:
                        phase = result.get("required_phase_observed")
                        if phase is None or count <= phase["output_bytes_when_observed"] + post_marker_margin:
                            result["status"] = "insufficient_phase_coverage"
                            break
                    # Upstream appends its emitted bytes; its final SFX rewrite
                    # has not happened. Freeze the owned group before reading.
                    os.killpg(process.pid, signal.SIGSTOP)
                    with target.open("rb") as file:
                        prefix = file.read(count)
                    if len(prefix) != count:
                        raise ValueError("output shrank before prefix capture")
                    snapshot = work / "coder-prefix.bin"
                    snapshot.write_bytes(prefix)
                    result.update(status="prefix_captured", prefix_bytes=count,
                                  prefix_sha256=digest(snapshot),
                                  output_bytes_at_stop=target.stat().st_size)
                    break
                if time.monotonic() - started >= timeout:
                    result["status"] = "timeout"
                    break
                time.sleep(0.25)
        finally:
            # Include surviving children even if the original parent exited.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            result["exit_code"] = process.wait()
            result["wall_seconds_to_stop"] = time.monotonic() - started
    result["log_sha256"] = digest(work / "run.log")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packages", "enwik9", "protocol", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if (platform.system(), platform.machine()) != ("Linux", "x86_64"):
        parser.error("requires native Linux x86-64")
    protocol = json.loads(args.protocol.read_text())
    corpus = args.enwik9.resolve()
    if corpus.stat().st_size != 1000000000 or digest(corpus) != protocol["enwik9_sha256"]:
        raise ValueError("requires official full enwik9")
    if shutil.disk_usage(args.output.parent.resolve()).free < 30 * 1024**3:
        raise ValueError("requires 30 GiB free scratch space before starting")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "release-full-input-prefix-comparison", "version": 1,
              "protocol_sha256": digest(args.protocol), "script_sha256": digest(Path(__file__)),
              "commit": capture("git", "rev-parse", "HEAD"), "platform": platform.platform(),
              "cpu": capture("lscpu"), "enwik9_sha256": digest(corpus),
              "runs": {}, "passed": False,
              "scope": "Intentionally stopped full-input release encodings. Equal-length emitted prefixes are compared by hash, not size. No complete archive, independent decode, full-corpus ratio, or resource eligibility claim; RSS is sampled only."}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    shutil.copyfile(args.protocol, output / "protocol.json")
    save()
    for role in ("baseline", "candidate"):
        package_dir = args.packages / ("release-" + role)
        binary = package_dir / "comp9"
        frozen = protocol["packages"][role]
        if digest(binary) != frozen["compressor_sha256"]:
            raise ValueError("release executable differs from frozen protocol: " + role)
        structure, _ = inspect(binary.read_bytes())
        if structure["blocks"]["weights"]["sha256"] != frozen["weights_sha256"]:
            raise ValueError("release weights differ")
        work = output / role
        work.mkdir()
        shutil.copyfile(binary, work / "comp9")
        (work / "comp9").chmod(0o755)
        os.link(corpus, work / "enwik9")
        command = ["./comp9", "-e", "enwik9", "archive9"]
        print(role, "starting the frozen release binary on full enwik9", flush=True)
        result = capture_prefix(command, work, work / "archive9", protocol["prefix_bytes"],
                                protocol["timeout_per_run_seconds"], protocol.get("required_log_marker"),
                                protocol.get("post_marker_output_margin_bytes", 0))
        result["compressor_sha256"] = digest(binary)
        result["package_report_sha256"] = digest(package_dir / "report.json")
        result["stages"] = {}
        report["runs"][role] = result
        save()
        if result["status"] != "prefix_captured":
            return 1
        for name, expected in protocol["stages"].items():
            path = work / name
            actual = {"bytes": path.stat().st_size, "sha256": digest(path)}
            result["stages"][name] = {**actual, "matches_reference": actual == expected}
            save()
            if actual != expected:
                raise ValueError("full release preparation differs: " + name)
        dictionary = work / ".dict.comp"
        result["compressed_dictionary"] = {"bytes": dictionary.stat().st_size, "sha256": digest(dictionary)}
        save()
        print(role, "captured", result["prefix_bytes"], "bytes; canonical stages verified", flush=True)
    a, b = (report["runs"][role] for role in ("baseline", "candidate"))
    report["prefixes_identical"] = a["prefix_sha256"] == b["prefix_sha256"]
    report["compressed_dictionaries_identical"] = a["compressed_dictionary"] == b["compressed_dictionary"]
    report["passed"] = report["prefixes_identical"] and report["compressed_dictionaries_identical"]
    save()
    print("Bounded release comparison:", "PASS" if report["passed"] else "FAIL")
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
