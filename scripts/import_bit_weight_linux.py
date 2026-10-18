#!/usr/bin/env python3
"""Verify a downloaded native Linux bit-weight artifact and retain bounded evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
VARIANT = "bit-weight-warm-start-lr3000-v1"
MODEL_SHA = "bfd6401b0142441e7b99a4fe930943d830e7dca2e47d08692e83b023a642f8e0"
SOURCE_PROTOCOL = ROOT / "benchmarks/training/20261017-bitl-archive-protocol-v1/protocol.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-role", type=Path, required=True,
                        help="downloaded artifact directory containing comparison/, run-*/ and host.json")
    parser.add_argument("--enwik8", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    src = args.artifact_role
    role = src.name
    if role not in ("screen", "holdout"):
        raise ValueError("artifact role must be screen or holdout")
    comparison = json.loads((src / "comparison/report.json").read_text())
    protocol = json.loads((src / "protocol.json").read_text())
    manifest = json.loads((src / "manifest.json").read_text())
    source_protocol = json.loads(SOURCE_PROTOCOL.read_text())
    host = json.loads((src / "host.json").read_text())
    checks = {}

    def check(label, okay):
        checks[label] = bool(okay)
        if not okay:
            raise ValueError("artifact check failed: " + label)

    check("source revision", host["commit"] == args.head_sha)
    check("source protocol", protocol["parent_protocol_sha256"] == digest(SOURCE_PROTOCOL)
          and source_protocol["model_sha256"] == MODEL_SHA)
    check("protocol", digest(src / "protocol.json") == comparison["protocol_sha256"])
    check("manifest", digest(src / "manifest.json") == comparison["manifest_sha256"])
    check("model names", list(comparison["variants"]) == ["baseline", VARIANT])
    check("fixture identity", protocol["fixtures"][role]["input_sha256"] == comparison["input_sha256"]
          and protocol["fixtures"][role]["manifest_sha256"] == comparison["manifest_sha256"])
    check("prepared input", digest(src / "fixture/upstream.ready") == comparison["input_sha256"])
    with args.enwik8.open("rb") as file:
        file.seek(manifest["source_offset"])
        original = file.read(manifest["raw_bytes"])
    check("official corpus", args.enwik8.stat().st_size == manifest["source_bytes"]
          and digest(args.enwik8) == manifest["source_sha256"])
    check("raw source segment", hashlib.sha256(original).hexdigest() == comparison["raw_sha256"])
    check("fixture replay", all(row["original_bytes_roundtrip"] and row["matches_expected"]
          for row in json.loads((src / "fixture/replay-report.json").read_text())["samples"].values()))
    a, b = comparison["variants"].values()
    check("trained model", b["model"]["model_sha256"] == MODEL_SHA
          and b["model"] == json.loads((src / f"build-{VARIANT}/build.json").read_text())["bit_weight_variant"])
    check("context identity", a["context"] == b["context"])
    check("payload improved", b["payload_bytes"] < a["payload_bytes"]
          and b["delta_bytes_vs_baseline"] == b["payload_bytes"]-a["payload_bytes"])
    for name, row in comparison["variants"].items():
        run = src / ("run-" + name)
        check(name + " archive", digest(run / "payload.cmix") == row["archive_sha256"]
              and (run / "payload.cmix").stat().st_size == row["payload_bytes"])
        check(name + " prepared roundtrip", digest(run / "restored") == comparison["input_sha256"])
        check(name + " original roundtrip", row["original_bytes_roundtrip"]
              and row["restored_raw_sha256"] == comparison["raw_sha256"])
        check(name + " binary", digest(run / "cmix") == row["binary_sha256"]
              and (run / "cmix").stat().st_size == row["binary_bytes"])
        for filename, field in (("metadata.json", "metadata_sha256"), ("results.jsonl", "results_sha256")):
            check(name + " " + filename, digest(src / "comparison" / name / filename) == row[field])
        for phase in ("compress", "decompress"):
            check(name + " " + phase + " log",
                  digest(src / "comparison" / (name + "-" + phase + ".log")) == row["log_sha256"][phase])
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    for file in src.rglob("*"):
        if file.is_file() and file.suffix in (".json", ".jsonl", ".log"):
            dest = out / file.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest)
    inventory = {str(file.relative_to(out)): digest(file) for file in sorted(out.rglob("*")) if file.is_file()}
    (out / "verification.json").write_text(json.dumps({"version": 1, "run_id": args.run_id,
        "head_sha": args.head_sha, "role": role, "checks": checks, "retained_sha256": inventory}, indent=2) + "\n")
    print(json.dumps({"role": role, "checks": len(checks), "files": len(inventory),
                      "payload_delta_bytes": b["delta_bytes_vs_baseline"]}, indent=2))


if __name__ == "__main__":
    main()
