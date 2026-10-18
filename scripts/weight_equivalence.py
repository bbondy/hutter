#!/usr/bin/env python3
"""Verify bound weight experiments, with explicit identity or tradeoff protocols."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from cmix_fixture_support import context_report, corpus_arguments, validate_context
from cmix_variants import model_identity
from cmix_weight_support import HEADER, WEIGHTS, fingerprint, stamp
from make_samples import digest
from model_history import validate_runner
from order_history import checked_restoration


def tradeoff(base, candidate, raw_bytes):
    if raw_bytes <= 0:
        raise ValueError("tradeoff requires a nonempty raw fixture")
    payload = candidate["payload_bytes"] - base["payload_bytes"]
    containers = 2 * (candidate["weight_bytes"] - base["weight_bytes"])
    numerator = payload * 1_000_000_000 + containers * raw_bytes
    return {"payload_delta_bytes": payload, "gross_two_container_delta_bytes": containers,
            "break_even_fixture_payload_delta_bytes": -containers * raw_bytes / 1_000_000_000,
            "projected_full_payload_delta_bytes": payload * 1_000_000_000 / raw_bytes,
            "projected_payload_plus_containers_delta_bytes": numerator / raw_bytes,
            "within_gross_budget": numerator < 0,
            "scope": "Proportional raw-byte screening heuristic; excludes executable changes, model-state differences and sampling error. Not a full-corpus score."}


def verify(args):
    protocol = json.loads(args.protocol.read_text())
    mode = protocol.get("acceptance_mode", "archive-identity")
    if mode not in ("archive-identity", "payload-tradeoff"):
        raise ValueError("unknown weight acceptance mode")
    if mode == "payload-tradeoff" and protocol.get("corpus_raw_bytes") != 1_000_000_000:
        raise ValueError("tradeoff protocol must explicitly declare full enwik9 size")
    manifest = json.loads(args.manifest.read_text())
    fixture = protocol["fixtures"][args.role]
    if digest(args.manifest) != fixture["manifest_sha256"]:
        raise ValueError("fixture manifest differs from protocol")
    sample = next(row for row in manifest["samples"] if row["variant"] == "upstream")
    if sample["sha256"] != fixture["input_sha256"]:
        raise ValueError("prepared input differs from protocol")
    helper = args.build.resolve() / "prepare-sample"
    if digest(helper) != manifest["helper_sha256"]:
        raise ValueError("inverse helper differs")
    runs = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    metas = {name: json.loads((run / "metadata.json").read_text()) for name, run in runs.items()}
    base, cand = (metas[name]["build"] for name in ("baseline", "candidate"))
    if any(model_identity(build)[0] != "baseline" for build in (base, cand)):
        raise ValueError("weight comparison changes other model parameters")
    for key in ("upstream_commit", "simde_commit", "compiler", "fixture_support",
                "preprocessing_support", "initialization", "platform", "machine"):
        if key not in base or base[key] != cand.get(key):
            raise ValueError("uncontrolled build difference: " + key)
    commands = [[part for part in build["command"] if not re.fullmatch(r"-j\d+", part)]
                for build in (base, cand)]
    if commands[0] != commands[1]:
        raise ValueError("compiler commands differ")
    binding = cand.get("weight_binding")
    if base.get("weight_binding") or not binding:
        raise ValueError("requires original baseline and explicitly bound candidate")
    if (binding["original_sha256"] != protocol["original_container_sha256"]
            or binding["container_sha256"] != protocol["candidate_container_sha256"]):
        raise ValueError("container identity differs from protocol")
    header = args.build / "source" / HEADER
    if digest(header) != base["source_files"][HEADER]["sha256"]:
        raise ValueError("baseline header changed")
    expected_header = hashlib.sha256(stamp(header.read_text(), int(binding["fingerprint_fnv1a64"], 16)).encode()).hexdigest()
    if (cand["source_files"][HEADER]["sha256"] != expected_header
            or binding["before_header_sha256"] != digest(header)
            or binding["after_header_sha256"] != expected_header):
        raise ValueError("candidate changes more than the stamped fingerprint")
    files = [{k: v for k, v in build["source_files"].items() if k not in (HEADER, WEIGHTS)}
             for build in (base, cand)]
    if files[0] != files[1]:
        raise ValueError("candidate changes other sources")
    for key in ("platform", "machine", "cpu", "native_arguments"):
        if metas["baseline"][key] != metas["candidate"][key]:
            raise ValueError("trial environment differs: " + key)
    if metas["baseline"]["side_data"]["dictionary/english.dic"] != metas["candidate"]["side_data"]["dictionary/english.dic"]:
        raise ValueError("dictionaries differ")
    records, logs = {}, []
    with tempfile.TemporaryDirectory(prefix="weight-equivalence-") as tmp:
        for name, run in runs.items():
            meta = metas[name]
            validate_runner(meta, protocol)
            if meta["native_arguments"] != corpus_arguments(manifest, meta["build"]):
                raise ValueError("fixture phases differ")
            if digest(run / "cmix") != meta["binary_sha256"] or meta["binary_sha256"] != meta["build"]["binary_sha256"]:
                raise ValueError("trial binary changed")
            rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
            if len(rows) != 1:
                raise ValueError("requires one complete trial per model")
            row = rows[0]
            if ((row["input_sha256"], row["input_bytes"]) != (sample["sha256"], sample["bytes"])
                    or not row["roundtrip"] or not row.get("context_valid")
                    or any(row[p]["status"] != "ok" for p in ("compress", "decompress"))):
                raise ValueError("trial input or round trip failed")
            archive, restored = (Path(row[p]["command"][-1]) for p in ("compress", "decompress"))
            if (digest(archive) != row["archive_sha256"] or archive.stat().st_size != row["archive_bytes"]
                    or digest(restored) != sample["sha256"]):
                raise ValueError("saved trial output differs")
            for asset, info in meta["side_data"].items():
                path = restored.parent / ("dictionary.dic" if asset == "dictionary/english.dic" else asset)
                if digest(path) != info["sha256"] or path.stat().st_size != info["bytes"]:
                    raise ValueError("trial asset changed")
            weight = restored.parent / WEIGHTS
            expected = protocol["original_container_sha256" if name == "baseline" else "candidate_container_sha256"]
            if digest(weight) != expected or meta["build"]["source_files"][WEIGHTS]["sha256"] != expected:
                raise ValueError("unexpected trial weight container")
            if name == "candidate" and fingerprint(weight) != int(binding["fingerprint_fnv1a64"], 16):
                raise ValueError("candidate fingerprint does not match its container")
            context = {phase: context_report(Path(row[phase]["log"])) for phase in ("compress", "decompress")}
            validate_context(context["compress"], context["decompress"], manifest)
            raw = Path(tmp) / (name + ".xml")
            subprocess.run([str(helper), *manifest["helper_arguments"], "decode", str(restored), str(raw)], check=True)
            raw_sha = checked_restoration(raw.read_bytes(), sample, manifest)
            records[name] = {"archive_sha256": digest(archive), "payload_bytes": archive.stat().st_size,
                             "restored_raw_sha256": raw_sha, "original_bytes_roundtrip": True,
                             "context": context, "binary_sha256": meta["binary_sha256"],
                             "binary_bytes": meta["binary_bytes"], "weight_bytes": weight.stat().st_size,
                             "metadata_sha256": digest(run / "metadata.json"),
                             "results_sha256": digest(run / "results.jsonl"),
                             "log_sha256": {p: digest(Path(row[p]["log"])) for p in ("compress", "decompress")}}
            logs.extend((Path(row[p]["log"]), name + "-" + p + ".log") for p in ("compress", "decompress"))
    same_archive = records["baseline"]["archive_sha256"] == records["candidate"]["archive_sha256"]
    same_context = records["baseline"]["context"] == records["candidate"]["context"]
    report = {"kind": "weight-archive-equivalence", "version": 1, "role": args.role,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "protocol_sha256": digest(args.protocol), "manifest_sha256": digest(args.manifest),
              "verifier_sha256": digest(Path(__file__)), "input_sha256": sample["sha256"],
              "archives_identical": same_archive, "context_identical": same_context,
              "passed": same_archive and same_context, "variants": records,
              "scope": "Fixture archives and exact original restoration; full prize package savings remain unverified."}
    if mode == "payload-tradeoff":
        report.update(kind="weight-payload-tradeoff", passed=same_context,
                      acceptance_mode=mode,
                      tradeoff=tradeoff(records["baseline"], records["candidate"], manifest["raw_bytes"]),
                      scope="Intentional model change: exact original restoration and fixed context; payload versus model-size screening, not archive identity or a prize score.")
    args.output.mkdir(parents=True, exist_ok=False)
    for name, run in runs.items():
        (args.output / name).mkdir()
        for file in ("metadata.json", "results.jsonl"):
            shutil.copyfile(run / file, args.output / name / file)
    for path, name in logs:
        shutil.copyfile(path, args.output / name)
    for path, name in ((args.manifest, "manifest.json"), (args.protocol, "protocol.json")):
        shutil.copyfile(path, args.output / name)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(args.role, "PASS" if report["passed"] else "FAIL", mode, "; raw XML restored")
    if mode == "payload-tradeoff":
        print(json.dumps(report["tradeoff"], indent=2))
    return int(not report["passed"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("protocol", "manifest", "build", "baseline", "candidate", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--role", choices=("screen", "holdout"), required=True)
    args = parser.parse_args()
    return verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
