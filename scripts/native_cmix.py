#!/usr/bin/env python3
"""Build and benchmark the experimental native ARM64 Mac cmix-neif port."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

from benchmark import capture, measured
from benchmark_history import record
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
from cmix_parity_support import instrument, SUPPORT
from cmix_fixture_support import instrument_fixture, provenance as fixture_provenance, corpus_arguments, context_report, validate_context
from cmix_variants import VARIANTS, apply_variant

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "engines/ports/cmix-neif-macos"
SIMDE_URL = "https://github.com/simd-everywhere/simde.git"
SIMDE_COMMIT = "71fd833d9666141edcd1d3c109a80e228303d8d7"  # v0.8.2, MIT
WEIGHTS = "weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4"
CODEC = "cmix-neif-macos-simde-dict"


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def build(args):
    upstream = json.loads(MANIFEST.read_text())
    delta = differences(upstream["files"], inventory(ENGINE))
    if any(delta.values()):
        raise ValueError(f"pinned upstream was modified: {delta}")
    destination = args.output.resolve()
    if destination.is_relative_to(ENGINE) or destination.is_relative_to(PORT):
        raise ValueError("build output must be outside the upstream and port directories")
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / "source"
    shutil.copytree(ENGINE, source)
    # All modifications are confined to the disposable build copy.
    shutil.copytree(PORT / "overlay", source, dirs_exist_ok=True)
    with (PORT / "port.patch").open("rb") as patch:
        subprocess.run(["patch", "-p1", "--batch"], cwd=source, stdin=patch, check=True)
    model_variant = apply_variant(source, args.variant)
    instrument_fixture(source)
    instrument(source, portable_random=True)
    simde = destination / "simde"
    subprocess.run(["git", "init", "-q", str(simde)], check=True)
    subprocess.run(["git", "-C", str(simde), "fetch", "--depth=1", SIMDE_URL, SIMDE_COMMIT], check=True)
    subprocess.run(["git", "-C", str(simde), "checkout", "--detach", "FETCH_HEAD"], check=True)
    if capture("git", "-C", str(simde), "rev-parse", "HEAD") != SIMDE_COMMIT:
        raise ValueError("SIMDe commit mismatch")
    # Run cancellation/tie probes under both classes of upstream FP flags.
    for fp in ("precise", "fast"):
        check = destination / f"check-simd-{fp}"
        flags = [f"-ffp-model={fp}"] + (["-ffp-contract=off"] if fp == "precise" else [])
        subprocess.run(["clang++", "-O3", "-std=c++17", *flags, "-Isrc", "-I../simde",
                        str(PORT / "check_simd.cpp"), "-o", str(check)], cwd=source, check=True)
        subprocess.run([str(check)], check=True)
    command = ["make", f"-j{args.jobs}", "CC=clang++ -Isrc -I../simde", "cmix"]
    metadata = {
        "kind": "experimental-native-build", "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "upstream_commit": upstream["commit"], "simde_commit": SIMDE_COMMIT,
        "simde_url": SIMDE_URL, "platform": platform.platform(), "machine": platform.machine(),
        "compiler": capture("clang++", "--version"), "command": command,
        "port_files": inventory(PORT), "parity_files": inventory(SUPPORT),
        "fixture_support": fixture_provenance(),
        "model_variant": model_variant,
        "initialization": "explicit glibc-compatible generator", "source_files": inventory(source),
        "scope": "Unpacked dictionary-mode development binary; no Linux RSS clamp, PGO or submission packaging.",
    }
    started = time.monotonic()
    with (destination / "build.log").open("wb") as log:
        result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
    metadata.update(exit_code=result.returncode, wall_seconds=time.monotonic() - started)
    if result.returncode == 0:
        metadata["binary_sha256"] = digest(source / "cmix")
        metadata["binary_bytes"] = (source / "cmix").stat().st_size
    write_json(destination / "build.json", metadata)
    result.check_returncode()
    helper_command = ["clang++", "-O2", "-std=c++17", "-Isrc", str(PORT / "prepare_sample.cpp"),
                      "-o", str(destination / "prepare-sample")]
    with (destination / "prepare-build.log").open("wb") as log:
        subprocess.run(helper_command, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
    metadata["sample_helper"] = {"command": helper_command, "sha256": digest(destination / "prepare-sample")}
    write_json(destination / "build.json", metadata)
    print(f"Built {source / 'cmix'}; provenance: {destination / 'build.json'}")


def samples(args):
    source = args.enwik8.resolve()
    if source.stat().st_size != 100_000_000 or digest(source, "sha1") != "57b8363b814821dc9d47aa4d41f58733519076b2":
        raise ValueError("sample preparation requires checksum-verified official enwik8")
    build_dir = args.build.resolve()
    provenance = json.loads((build_dir / "build.json").read_text())
    helper = build_dir / "prepare-sample"
    if digest(helper) != provenance["sample_helper"]["sha256"]:
        raise ValueError("sample helper differs from its build record")
    data = source.read_bytes()
    start = data.find(b"  <page>\n", args.start_offset)
    if start < 0:
        raise ValueError("no complete article starts at or after the requested offset")
    end_marker = b"  </page>\n"
    end = data.find(end_marker, start + args.target_bytes)
    if end < 0:
        raise ValueError("no complete article ends after the target sample size")
    end += len(end_marker)
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    raw, ready, restored = [destination / name for name in ("articles.xml", "articles.ready", "articles.restored")]
    raw.write_bytes(data[start:end])
    subprocess.run([str(helper), "encode", str(raw), str(ready)], check=True)
    subprocess.run([str(helper), "decode", str(ready), str(restored)], check=True)
    if digest(raw) != digest(restored):
        raise ValueError("sample preprocessing did not round-trip")
    manifest = {
        "version": 1, "source": str(source), "source_bytes": len(data), "source_sha256": digest(source),
        "source_requested_offset": args.start_offset,
        "source_offset": start, "source_end": end, "raw_bytes": raw.stat().st_size,
        "raw_sha256": digest(raw), "preprocessing_roundtrip": True,
        "page_count": data[start:end].count(b"  <page>\n"),
        "preprocessing": "upstream phda9 on complete articles in original order; no full-corpus reorder or census/comment-index transforms",
        "helper_sha256": digest(helper), "upstream_commit": provenance["upstream_commit"],
        "samples": [{"path": str(ready), "bytes": ready.stat().st_size,
                     "sha256": digest(ready), "role": "held-out" if args.start_offset else "native-feasibility"}],
    }
    write_json(destination / "manifest.json", manifest)
    print(f"Prepared and restored {raw.stat().st_size} raw bytes; coder input: {ready}")


def bench(args):
    build_dir = args.build.resolve()
    provenance = json.loads((build_dir / "build.json").read_text())
    source = build_dir / "source"
    if provenance.get("binary_sha256") != digest(source / "cmix"):
        raise ValueError("binary does not match its build record")
    for name in (WEIGHTS, "dictionary/english.dic"):
        if digest(source / name) != provenance["source_files"][name]["sha256"]:
            raise ValueError(f"asset does not match build record: {name}")
    inputs = [p.resolve() for p in args.inputs]
    if not all(p.is_file() for p in inputs):
        raise ValueError("all inputs must be existing files")
    native_args = []
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
        known = {s["sha256"]: s["bytes"] for s in manifest["samples"]}
        if any(known.get(digest(p)) != p.stat().st_size for p in inputs):
            raise ValueError("manifest does not describe every input; refusing an expensive unmatched run")
        if "page_count" in manifest:
            native_args = corpus_arguments(manifest, provenance)
    run = args.output.resolve()
    run.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source / "cmix", run / "cmix")
    metadata = {
        "schema_version": 1, "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "git_status": capture("git", "-C", str(ROOT), "status", "--porcelain"),
        "platform": platform.platform(), "machine": platform.machine(),
        "cpu": capture("sysctl", "-n", "machdep.cpu.brand_string"),
        "runner_sha256": digest(Path(__file__)), "binary_sha256": digest(run / "cmix"),
        "binary_bytes": (run / "cmix").stat().st_size, "build": provenance,
        "timeout_seconds": args.timeout, "repeats": args.repeats,
        "native_arguments": native_args,
        "size_scope": "Payload only; external dictionary and weights required. Not a Hutter Prize score.",
        "side_data": {name: {"bytes": (source / name).stat().st_size, "sha256": digest(source / name)}
                      for name in (WEIGHTS, "dictionary/english.dic")},
    }
    write_json(run / "metadata.json", metadata)
    failed = False
    hashes = {}
    original_cwd = Path.cwd()
    try:
        with (run / "results.jsonl").open("w") as results:
            for index, input_file in enumerate(inputs):
                for repeat in range(args.repeats):
                    trial = run / f"trial-{index}-{repeat}"
                    trial.mkdir()
                    for asset, dest in ((WEIGHTS, WEIGHTS), ("dictionary/english.dic", "dictionary.dic")):
                        shutil.copyfile(source / asset, trial / dest)
                    # Upstream writes fixed-name scratch files and loads weights from cwd.
                    os.chdir(trial)
                    archive, restored = trial / "payload.cmix", trial / "restored"
                    enc = [str(run / "cmix"), *native_args, "-c", "dictionary.dic", str(input_file), str(archive)]
                    dec = [str(run / "cmix"), *native_args, "-d", "dictionary.dic", str(archive), str(restored)]
                    row = {"input": str(input_file), "input_sha256": digest(input_file),
                           "input_bytes": input_file.stat().st_size, "codec": CODEC,
                           "repeat": repeat, "roundtrip": False, "size_scope": "payload-only"}
                    row["compress"] = measured(enc, trial / "compress.log", args.timeout)
                    if row["compress"]["status"] == "ok" and archive.is_file():
                        row["archive_bytes"] = archive.stat().st_size
                        row["archive_sha256"] = digest(archive)
                        previous = hashes.setdefault(row["input_sha256"], row["archive_sha256"])
                        row["repeat_matches"] = previous == row["archive_sha256"]
                        row["decompress"] = measured(dec, trial / "decompress.log", args.timeout)
                        row["roundtrip"] = (row["decompress"]["status"] == "ok" and restored.is_file()
                                            and digest(restored) == row["input_sha256"])
                    if native_args and native_args[0] == "--native-corpus" and row["roundtrip"]:
                        row["context"] = {phase: context_report(Path(row[phase]["log"]))
                                          for phase in ("compress", "decompress")}
                        try:
                            validate_context(row["context"]["compress"], row["context"]["decompress"], manifest)
                            if manifest["redirect_prefix_count"] < manifest["page_count"]:
                                if any("entering main text block" not in Path(row[phase]["log"]).read_text(errors="replace")
                                       for phase in ("compress", "decompress")):
                                    raise ValueError("main text phase was not observed")
                            row["context_valid"] = True
                        except ValueError as error:
                            row["context_valid"] = False
                            row["context_error"] = str(error)
                    if not row["roundtrip"]:
                        row["failure_log_tails"] = {
                            phase: Path(row[phase]["log"]).read_text(errors="replace")[-8192:]
                            for phase in ("compress", "decompress") if phase in row
                        }
                    failed |= not row["roundtrip"] or not row.get("repeat_matches", True) or not row.get("context_valid", True)
                    results.write(json.dumps(row) + "\n")
                    results.flush()
                    print(json.dumps(row), flush=True)
    finally:
        os.chdir(original_cwd)
    if args.record:
        record(run, args.record, args.note, args.manifest)
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("build")
    compile_parser.add_argument("--output", type=Path, default=ROOT / "build/native-cmix")
    compile_parser.add_argument("--jobs", type=int, default=8)
    compile_parser.add_argument("--variant", choices=VARIANTS, default="baseline")
    sample = sub.add_parser("samples")
    sample.add_argument("--enwik8", type=Path, default=ROOT / "data/enwik8")
    sample.add_argument("--build", type=Path, default=ROOT / "build/native-cmix")
    sample.add_argument("--output", type=Path, required=True)
    sample.add_argument("--target-bytes", type=int, default=100_000)
    sample.add_argument("--start-offset", type=int, default=0,
                        help="first complete article beginning at or after this enwik8 byte offset")
    test = sub.add_parser("bench")
    test.add_argument("inputs", type=Path, nargs="+")
    test.add_argument("--build", type=Path, default=ROOT / "build/native-cmix")
    test.add_argument("--output", type=Path, required=True)
    test.add_argument("--timeout", type=float, default=1800)
    test.add_argument("--repeats", type=int, default=1)
    test.add_argument("--record")
    test.add_argument("--note", default="")
    test.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        parser.error("this experimental port is scoped to macOS ARM64")
    if args.command == "build" and args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.command == "samples" and (not 0 < args.target_bytes < 99_000_000 or
                                       not 0 <= args.start_offset < 100_000_000):
        parser.error("sample target and start offset must fit enwik8")
    if args.command == "bench":
        if args.timeout <= 0 or args.repeats < 1:
            parser.error("timeout and repeats must be positive")
        if args.record:
            import re
            from benchmark_history import ROOT as HISTORY
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.record) or not args.note:
                parser.error("--record needs a simple unique ID and a nonempty --note")
            if (HISTORY / args.record).exists():
                parser.error("history ID already exists")
    try:
        return {"build": build, "samples": samples, "bench": bench}[args.command](args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
