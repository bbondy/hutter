#!/usr/bin/env python3
"""Build the public CPU trainer and verify frozen replay against live probabilities."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import time

from benchmark import capture
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
from native_cmix import PORT, SIMDE_COMMIT
import cmix_bit_trace_support as trace_support

ROOT = Path(__file__).resolve().parents[1]
BF16_SHA = "c72957f48c2ec81afa3aed2baae7acd964c17f96bb0406b8195818fc708a8e7d"
OPEN_CHECK = r'''
  const char* expected_path = std::getenv("HUTTER_EXPECT_PROBABILITIES");
  FILE* expected_probabilities = expected_path ? std::fopen(expected_path, "rb") : nullptr;
  if (!expected_probabilities) {
    std::fprintf(stderr, "replay verification requires live probabilities\n"); return 5;
  }
'''
CHECK_ONE = r'''
      uint16_t expected_q = 0;
      if (std::fread(&expected_q, 2, 1, expected_probabilities) != 1) {
        std::fprintf(stderr, "replay verification short probabilities at %llu\n", nbits); return 5;
      }
      if (q != expected_q) {
        std::fprintf(stderr, "replay probability mismatch at bit %llu: live=%u replay=%u\n",
                     nbits, (unsigned int)expected_q, q); return 6;
      }
'''
CLOSE_CHECK = r'''
  if (!nbits || std::ferror(f) || std::ferror(fa) ||
      std::fgetc(expected_probabilities) != EOF || std::ferror(expected_probabilities) ||
      std::fgetc(fa) != EOF) {
    std::fprintf(stderr, "replay verification incomplete input or extra records\n"); return 5;
  }
  std::fclose(expected_probabilities);
  std::fprintf(stderr, "CMIX_BITL_REPLAY {\"bits\":%llu,\"integer_probabilities_equal\":true}\n", nbits);
'''


def rewrite_verifier(text):
    anchors = ("  FILE* f = std::fopen(argv[1], \"rb\");",
               "      if (!meta_skip) bit_head::Observe(bit);", "  std::fclose(f);")
    if any(text.count(a) != 1 for a in anchors) or "HUTTER_EXPECT_PROBABILITIES" in text:
        raise ValueError("replay verifier anchor changed")
    for anchor, addition in zip(anchors, (OPEN_CHECK, CHECK_ONE, CLOSE_CHECK)):
        text = text.replace(anchor, addition + anchor)
    return text


def save(path, report):
    path.write_text(json.dumps(report, indent=2) + "\n")


def provenance(kind):
    return {"kind": kind, "version": 1,
            "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
            "script_sha256": digest(Path(__file__)), "platform": platform.platform(), "passed": False}


def new_output(path):
    path = path.resolve()
    if path.is_relative_to(ENGINE) or path.is_relative_to(PORT):
        raise ValueError("output must be outside pinned source and port trees")
    path.mkdir(parents=True, exist_ok=False)
    return path


def build(args):
    upstream = json.loads(MANIFEST.read_text())
    if any(differences(upstream["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream differs")
    native = args.native_build.resolve()
    native_info = json.loads((native / "build.json").read_text())
    if native_info["platform"] != platform.platform() or native_info["exit_code"] != 0:
        raise ValueError("requires a successful native build on this platform")
    darwin = platform.system() == "Darwin"
    compiler = "clang++" if darwin else "clang++-18"
    compiler_info = capture(compiler, "--version")
    if compiler_info != native_info["compiler"]:
        raise ValueError("compiler differs from live model build")
    out = new_output(args.output)
    source = out / "source"
    shutil.copytree(ENGINE / "training/bitl/trainer", source)
    before = inventory(source)
    driver = source / "replay_trainer.cpp"
    driver.write_text(rewrite_verifier(driver.read_text()))
    flags = ["-O3", "-std=c++17", "-ffp-model=precise", "-ffp-contract=off",
             "-fno-math-errno", "-fno-builtin", "-fno-exceptions", "-fno-unwind-tables",
             "-fno-asynchronous-unwind-tables", "-fdata-sections", "-ffunction-sections",
             "-Wall", "-Wno-unused-variable"]
    if darwin:
        simde = native / "simde"
        if (capture("git", "-C", str(simde), "rev-parse", "HEAD") != SIMDE_COMMIT
                or capture("git", "-C", str(simde), "status", "--porcelain")):
            raise ValueError("SIMDe differs")
        header = native / "source/src/native_simd.h"
        if digest(header) != native_info["source_files"]["src/native_simd.h"]["sha256"]:
            raise ValueError("live SIMD compatibility header differs")
        shutil.copy2(header, source / "native_simd.h")
        (source / "isa_floor.h").write_text('#pragma once\n#include "native_simd.h"\n')
        model = source / "bit_head.cpp"
        text = model.read_text()
        if text.count("#include <immintrin.h>") != 1:
            raise ValueError("trainer SIMD include changed")
        model.write_text(text.replace("#include <immintrin.h>", '#include "native_simd.h"'))
        flags += ["-I" + str(simde)]
    else:
        flags += ["-m64", "-march=x86-64-v3", "-mtune=znver2", "-fno-pie"]
    command = [compiler, *flags, str(source / "bit_head.cpp"), str(driver),
               *([] if darwin else ["-no-pie"]), "-o", str(out / "replay")]
    report = {**provenance("bitl-frozen-replay-build"), "upstream_commit": upstream["commit"],
              "compiler": compiler_info, "command": command, "original_sources": before,
              "source_files": inventory(source), "live_build_sha256": digest(native / "build.json"),
              "simde_commit": SIMDE_COMMIT if darwin else None,
              "scope": "Original public trainer arithmetic; Mac uses the live port SIMD header. Added driver checks compare each integer probability, without changing model arithmetic."}
    save(out / "build.json", report)
    with (out / "build.log").open("wb") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    report.update(exit_code=result.returncode, log_sha256=digest(out / "build.log"))
    if result.returncode == 0:
        report.update(passed=True, binary_sha256=digest(out / "replay"))
    save(out / "build.json", report)
    result.check_returncode()


def verify(args):
    build_dir = args.build.resolve()
    build_info = json.loads((build_dir / "build.json").read_text())
    if (not build_info["passed"] or build_info["platform"] != platform.platform()
            or digest(build_dir / "replay") != build_info["binary_sha256"]
            or inventory(build_dir / "source") != build_info["source_files"]):
        raise ValueError("replay build changed or belongs to another platform")
    protocol = json.loads(args.protocol.read_text())
    if protocol["script_sha256"] != digest(Path(__file__)):
        raise ValueError("replay script differs from frozen protocol")
    if protocol["trace_support_sha256"] != digest(Path(trace_support.__file__)):
        raise ValueError("trace validation differs from frozen protocol")
    weights = args.weights.resolve()
    if digest(weights) != BF16_SHA or weights.stat().st_size != 7386:
        raise ValueError("requires exact shipped BF16 weights")
    comparison = json.loads((args.comparison / "report.json").read_text())
    if (comparison["protocol_sha256"] != protocol["trace_protocol_sha256"]
            or comparison["input_sha256"] not in protocol["fixture_input_sha256"]):
        raise ValueError("comparison differs from frozen fixtures")
    recorded = comparison["variants"]["bit-trace-fixture"]
    if not (recorded["unchanged_archive"] and recorded["trace_encoder_decoder_match"]
            and recorded["original_bytes_roundtrip"]):
        raise ValueError("requires accepted unchanged-archive trace comparison")
    run = args.run.resolve()
    meta = json.loads((run / "metadata.json").read_text())
    if digest(run / "metadata.json") != recorded["metadata_sha256"] or meta["build"]["compiler"] != build_info["compiler"]:
        raise ValueError("live run identity or compiler differs")
    directory = run / "trial-0-0"
    log = directory / "compress.log"
    if digest(log) != recorded["log_sha256"]["compress"]:
        raise ValueError("live trace log differs")
    trace = trace_support.inspect_log(log, directory)
    if trace != recorded["bit_trace"]:
        raise ValueError("trace files differ from accepted comparison")
    names = json.loads(re.findall(r'^CMIX_BITL_TRACE (\{[^\n]+\})$', log.read_text(), re.M)[0])
    out = new_output(args.output)
    env_values = {"REPLAY_CHANNEL": str(directory / names["channel"]), "REPLAY_LOAD": str(weights),
                  "REPLAY_FREEZE_AT": "1", "HUTTER_EXPECT_PROBABILITIES": str(directory / names["probability"])}
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("REPLAY_", "HUTTER_"))}
    command = [str(build_dir / "replay"), str(directory / names["trace"]), "0", "0"]
    report = {**provenance("bitl-frozen-replay-verification"), "comparison_sha256": digest(args.comparison / "report.json"),
              "protocol_sha256": digest(args.protocol), "build_sha256": digest(build_dir / "build.json"),
              "binary_sha256": build_info["binary_sha256"], "weights_sha256": digest(weights), "trace": trace,
              "command": command, "environment": env_values,
              "scope": "Fixture replay of shipped weights. Freeze after first Observe, before any complete 1024-bit backward window; no optimizer update. No training, archive improvement or full-stream online-learning equivalence claim."}
    shutil.copy2(args.protocol, out / "protocol.json")
    save(out / "report.json", report)

    def execute(label, overrides):
        path = out / (label + ".log")
        started = time.monotonic()
        with path.open("wb") as output:
            try:
                result = subprocess.run(command, env={**environment, **env_values, **overrides},
                                        cwd=out, stdout=output, stderr=subprocess.STDOUT, timeout=1200)
                code, status = result.returncode, "completed"
            except subprocess.TimeoutExpired:
                code, status = None, "timeout"
        return {"exit_code": code, "status": status, "wall_seconds": time.monotonic() - started,
                "log_sha256": digest(path)}

    report["replay"] = execute("replay", {})
    expected = {"bits": trace["bits"], "integer_probabilities_equal": True}
    matches = re.findall(r'^CMIX_BITL_REPLAY (\{[^\n]+\})$', (out / "replay.log").read_text(), re.M)
    report["probabilities_match"] = report["replay"]["exit_code"] == 0 and len(matches) == 1 and json.loads(matches[0]) == expected
    save(out / "report.json", report)
    # A deliberately wrong first probability must fail as a value mismatch,
    # not merely as a truncated file or another loader error.
    with (directory / names["probability"]).open("rb") as file:
        original = struct.unpack("<H", file.read(2))[0]
    changed = original + 1 if original < 65535 else 1
    negative = out / "wrong-first-probability.bin"
    negative.write_bytes(struct.pack("<H", changed))
    report["negative_control"] = execute("negative-control", {"HUTTER_EXPECT_PROBABILITIES": str(negative)})
    report["negative_control"].update(original_probability=original, changed_probability=changed,
                                      input_sha256=digest(negative))
    report["negative_control_rejected"] = (report["negative_control"]["exit_code"] == 6
        and "replay probability mismatch at bit 0:" in (out / "negative-control.log").read_text())
    report["passed"] = report["probabilities_match"] and report["negative_control_rejected"]
    save(out / "report.json", report)
    print(json.dumps({key: report[key] for key in ("passed", "probabilities_match", "negative_control_rejected")}, indent=2))
    return int(not report["passed"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compiler = sub.add_parser("build")
    compiler.add_argument("--native-build", type=Path, required=True)
    compiler.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    for key in ("build", "run", "comparison", "weights", "protocol", "output"):
        check.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    if (platform.system(), platform.machine()) not in (("Darwin", "arm64"), ("Linux", "x86_64")):
        parser.error("requires native Apple Silicon or Linux x86-64")
    try:
        return build(args) if args.command == "build" else verify(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
