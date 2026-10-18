#!/usr/bin/env python3
"""Run a frozen release through full enwik9 encoding and independent SFX decoding.

Requires a persistent native Linux x86-64 host. Sampled resource limits are
operational stop conditions, not proof of the contest's resource eligibility.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import time

from benchmark import capture
from make_samples import digest
from package_structure import inspect

ROOT = Path(__file__).resolve().parents[1]


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def process_tree(pid):
    """Include children of every thread, tolerating processes that just exited."""
    found, pending = set(), [pid]
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        for file in Path(f"/proc/{current}/task").glob("*/children"):
            try:
                pending.extend(map(int, file.read_text().split()))
            except (OSError, ValueError):
                pass
    return found


def sample_resources(pid, work):
    """Count regular-file inodes once, including open unlinked temporary files."""
    pids = process_tree(pid)
    rss, files = 0, {}

    def count(path, follow):
        try:
            info = path.stat() if follow else path.lstat()
            if stat.S_ISREG(info.st_mode):
                files[(info.st_dev, info.st_ino)] = (info.st_size, info.st_blocks * 512)
        except OSError:
            pass

    for path in work.rglob("*"):
        count(path, False)
    for current in pids:
        try:
            status = Path(f"/proc/{current}/status").read_text()
            rss += next((int(line.split()[1]) * 1024 for line in status.splitlines()
                         if line.startswith("VmRSS:")), 0)
        except (OSError, ValueError):
            pass
        for fd in Path(f"/proc/{current}/fd").glob("*"):
            count(fd, True)
    return {"process_tree_rss_bytes": rss,
            "apparent_regular_file_bytes": sum(size for size, _ in files.values()),
            "allocated_regular_file_bytes": sum(size for _, size in files.values()),
            "work_free_bytes": shutil.disk_usage(work).free,
            "tmp_free_bytes": shutil.disk_usage("/tmp").free}


def run_phase(command, work, limits, sampler=sample_resources):
    """Persist a heartbeat and terminate only this invocation's process group."""
    started = time.monotonic()
    report = {"command": command, "status": "running", "samples": 0,
              "sampled_peaks": {}, "sampling_interval_seconds": limits["sample_seconds"]}
    save_json(work / "phase.json", report)
    process = None
    try:
        with (work / "run.log").open("wb") as log:
            process = subprocess.Popen(command, cwd=work, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True,
                                       env={**os.environ, "LC_ALL": "C"})
            last_save = started
            while True:
                sample = sampler(process.pid, work)
                report["samples"] += 1
                report["last_sample"] = sample
                for key in ("process_tree_rss_bytes", "apparent_regular_file_bytes", "allocated_regular_file_bytes"):
                    report["sampled_peaks"][key] = max(report["sampled_peaks"].get(key, 0), sample[key])
                elapsed = time.monotonic() - started
                if sample["process_tree_rss_bytes"] > limits["rss_stop_bytes"]:
                    report["status"] = "sampled_rss_limit"
                    break
                if sample["apparent_regular_file_bytes"] > limits["scratch_stop_bytes"]:
                    report["status"] = "sampled_scratch_limit"
                    break
                if min(sample["work_free_bytes"], sample["tmp_free_bytes"]) < limits["minimum_free_bytes"]:
                    report["status"] = "low_disk_space"
                    break
                code = process.poll()
                if code is not None:
                    report["status"] = "ok" if code == 0 else "failed"
                    break
                if elapsed >= limits["phase_timeout_seconds"]:
                    report["status"] = "timeout"
                    break
                if time.monotonic() - last_save >= 60:
                    report["wall_seconds"] = elapsed
                    save_json(work / "phase.json", report)
                    print(work.name, round(elapsed), "seconds; sampled RSS", sample["process_tree_rss_bytes"], flush=True)
                    last_save = time.monotonic()
                time.sleep(limits["sample_seconds"])
    except BaseException as error:
        report.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "error",
                      error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            report["exit_code"] = process.wait()
        report["wall_seconds"] = time.monotonic() - started
        for name in ("run.log", "time.log"):
            if (work / name).is_file():
                report[name + "_sha256"] = digest(work / name)
        save_json(work / "phase.json", report)
    return report


def file_record(path):
    return {"bytes": path.stat().st_size, "sha256": digest(path)}


def execute(args):
    protocol = json.loads(args.protocol.read_text())
    frozen = protocol["packages"][args.role]
    corpus, binary = args.enwik9.resolve(), args.binary.resolve()
    if file_record(corpus) != protocol["input"]:
        raise ValueError("input differs from official enwik9")
    if file_record(binary) != frozen["compressor"]:
        raise ValueError("compressor differs from frozen release package")
    structure, _ = inspect(binary.read_bytes())
    if structure["blocks"]["weights"]["sha256"] != frozen["weights_sha256"]:
        raise ValueError("release weights differ")
    if args.cpu not in os.sched_getaffinity(0):
        raise ValueError("requested CPU is outside this process's allowed affinity")
    if not {"avx2", "fma"} <= set(Path("/proc/cpuinfo").read_text().split()):
        raise ValueError("host does not advertise AVX2 and FMA")
    if not shutil.which("taskset") or not Path("/usr/bin/time").is_file():
        raise ValueError("requires taskset and GNU /usr/bin/time")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < protocol["required_free_bytes"]:
        raise ValueError("insufficient free workspace for frozen full-run protocol")
    if shutil.disk_usage("/tmp").free < protocol["required_tmp_free_bytes"]:
        raise ValueError("insufficient /tmp space for upstream unnamed files")
    output.mkdir(exist_ok=False)
    shutil.copyfile(args.protocol, output / "protocol.json")
    report = {"kind": "release-full-enwik9-roundtrip", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "role": args.role, "protocol_sha256": digest(args.protocol),
              "script_sha256": digest(Path(__file__)),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "git_status": capture("git", "-C", str(ROOT), "status", "--porcelain"),
              "host": {"platform": platform.platform(), "lscpu": capture("lscpu"),
                       "memory": Path("/proc/meminfo").read_text(),
                       "cpu_affinity": args.cpu, "libc": capture("ldd", "--version")},
              "input": protocol["input"], "package_structure": structure,
              "resource_scope": "Sampled process-tree RSS and regular-file bytes, including open unlinked files; GNU time logs retained separately. No hard cgroup cap, all-machine disk audit, or prize eligibility certification.",
              "decoder_isolation": "Separate initially empty working directory supplied only with the SFX archive. This is not a filesystem/network sandbox.",
              "passed": False, "phases": {}}
    save = lambda: save_json(output / "report.json", report)
    save()
    try:
        enc, dec = output / "encode", output / "decode"
        enc.mkdir()
        # Copies prevent a malfunctioning executable from changing the caller's
        # input/binary and permit different source/work filesystems.
        shutil.copyfile(corpus, enc / "enwik9")
        shutil.copyfile(binary, enc / "comp9")
        (enc / "comp9").chmod(0o755)
        if file_record(enc / "enwik9") != protocol["input"] or file_record(enc / "comp9") != frozen["compressor"]:
            raise ValueError("frozen working copies differ")
        arguments = b"-e\nenwik9\narchive9\n"
        (output / "comp9.args").write_bytes(arguments)

        def measured(command, work):
            return run_phase(["/usr/bin/time", "-v", "-o", "time.log", "taskset", "-c", str(args.cpu), *command],
                             work, protocol["limits"])

        report["phases"]["encode"] = measured(["./comp9", "-e", "enwik9", "archive9"], enc)
        save()
        if report["phases"]["encode"]["status"] != "ok":
            return 1
        archive = enc / "archive9"
        report["archive"] = file_record(archive)
        report["matches_published_archive"] = (report["archive"] == frozen["expected_archive"]
                                                if frozen.get("expected_archive") else None)
        report["compressor_unchanged"] = file_record(enc / "comp9") == frozen["compressor"]
        report["input_unchanged"] = file_record(enc / "enwik9") == protocol["input"]
        report["packaged_bytes_with_arguments"] = frozen["compressor"]["bytes"] + report["archive"]["bytes"] + len(arguments)
        save()
        dec.mkdir()
        shutil.copyfile(archive, dec / "archive9")
        (dec / "archive9").chmod(0o755)
        if file_record(dec / "archive9") != report["archive"]:
            raise ValueError("decoder archive differs from completed encoding")
        report["decoder_initial_files"] = [p.name for p in dec.iterdir()]
        report["phases"]["decode"] = measured(["./archive9"], dec)
        save()
        restored = dec / "enwik9_uncompressed"
        report["restored"] = file_record(restored) if restored.is_file() else None
        report["original_bytes_roundtrip"] = report["restored"] == protocol["input"]
        report["passed"] = (report["phases"]["decode"]["status"] == "ok"
                            and report["original_bytes_roundtrip"] and report["input_unchanged"]
                            and report["compressor_unchanged"] and report["matches_published_archive"] is not False)
        save()
        return int(not report["passed"])
    except BaseException as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "enwik9", "protocol", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--role", choices=("baseline", "candidate"), default="baseline")
    parser.add_argument("--cpu", type=int, required=True, help="one allowed logical CPU; pin both phases")
    args = parser.parse_args()
    if (platform.system(), platform.machine()) != ("Linux", "x86_64"):
        parser.error("requires a persistent native Linux x86-64 host")
    try:
        return execute(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
