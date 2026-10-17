#!/usr/bin/env python3
"""Recreate every frozen article order with another platform's preparation helper."""
import argparse
import copy
import json
from pathlib import Path
import subprocess

from article_order import pages_from_bytes, sha
from cmix_fixture_support import corpus_arguments
from make_samples import digest
from order_history import checked_restoration


def replay(manifest_path, enwik8, build, output):
    original = json.loads(manifest_path.read_text())
    if enwik8.stat().st_size != original["source_bytes"] or digest(enwik8) != original["source_sha256"]:
        raise ValueError("source corpus differs from frozen fixture")
    data = enwik8.read_bytes()[original["source_offset"]:original["source_end"]]
    if sha(data) != original["raw_sha256"]:
        raise ValueError("raw source selection differs")
    pages = pages_from_bytes(data)
    by_id = {p["id"]: p["raw"] for p in pages}
    if len(by_id) != original["page_count"] or len(pages) != len(by_id):
        raise ValueError("fixture page IDs are incomplete or ambiguous")
    metadata = json.loads((build / "build.json").read_text())
    flags = corpus_arguments(original, metadata)
    helper = build.resolve() / "prepare-sample"
    if digest(helper) != metadata["sample_helper"]["sha256"]:
        raise ValueError("helper differs from build")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = copy.deepcopy(original)
    manifest["replayed_from_manifest_sha256"] = digest(manifest_path)
    manifest["original_helper_sha256"] = original["helper_sha256"]
    manifest["helper_sha256"] = digest(helper)
    manifest["source"] = str(enwik8.resolve())
    manifest["replay_script_sha256"] = digest(Path(__file__))
    checks = {"source_manifest_sha256": digest(manifest_path), "helper_sha256": digest(helper),
              "helper_arguments": flags, "samples": {}}
    for sample in manifest["samples"]:
        raw = output / (sample["variant"] + ".xml")
        ready = output / (sample["variant"] + ".ready")
        restored = output / (sample["variant"] + ".restored")
        raw.write_bytes(b"".join(by_id[pid] for pid in sample["page_ids"]))
        checked_restoration(raw.read_bytes(), sample, original)
        subprocess.run([str(helper), *flags, "encode", str(raw), str(ready)], check=True)
        row = {"bytes": ready.stat().st_size, "sha256": digest(ready),
               "expected_bytes": sample["bytes"], "expected_sha256": sample["sha256"],
               "original_bytes_roundtrip": False}
        row["matches_expected"] = (row["bytes"], row["sha256"]) == (sample["bytes"], sample["sha256"])
        checks["samples"][sample["variant"]] = row
        (output / "replay-report.json").write_text(json.dumps(checks, indent=2) + "\n")
        subprocess.run([str(helper), *flags, "decode", str(ready), str(restored)], check=True)
        checked_restoration(restored.read_bytes(), sample, original)
        row["original_bytes_roundtrip"] = True
        (output / "replay-report.json").write_text(json.dumps(checks, indent=2) + "\n")
        if not row["matches_expected"]:
            raise ValueError("platform preparation differs from frozen input; see replay-report.json")
        sample["path"] = str(ready)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Recreated all frozen prepared bytes and restored original articles:", output)
    return output / "manifest.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("manifest", "enwik8", "build", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    try:
        replay(args.manifest, args.enwik8, args.build, args.output)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
