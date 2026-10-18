#!/usr/bin/env python3
"""Compare measured release components without inventing a full archive score."""
import argparse
import json
from pathlib import Path

from make_samples import digest
from package_structure import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "protocol", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    base, cand = (json.loads(path.read_text()) for path in (args.baseline, args.candidate))
    protocol = json.loads(args.protocol.read_text())
    if not base["passed"] or not cand["passed"] or base["weight_binding"] or not cand["weight_binding"]:
        raise ValueError("requires passing original and explicitly bound release packages")
    for key in ("upstream_commit", "compiler", "linker", "packages", "platform", "cpu"):
        if base[key] != cand[key]:
            raise ValueError("uncontrolled package environment difference: " + key)
    for record in (base, cand):
        package = record["package"]
        folder = args.baseline.parent if record is base else args.candidate.parent
        if digest(folder / "comp9") != package["compressor_sha256"]:
            raise ValueError("built package differs from report")
        actual, decoder = inspect((folder / "comp9").read_bytes())
        if actual != package or (folder / "decoder-prefix").read_bytes() != decoder:
            raise ValueError("package component record or decoder prefix differs")
    a, b = base["package"], cand["package"]
    if (a["blocks"]["weights"]["sha256"] != protocol["original_container_sha256"]
            or b["blocks"]["weights"]["sha256"] != protocol["candidate_container_sha256"]):
        raise ValueError("package weights differ from frozen experiment")
    if any(a["blocks"][key] != b["blocks"][key] for key in ("hints", "order")):
        raise ValueError("embedded auxiliary blocks differ")
    keys = ("compressor_bytes", "packed_program_bytes", "decoder_prefix_bytes",
            "component_bytes_excluding_dictionary_payload_footer_args")
    report = {"kind": "release-component-comparison", "version": 1,
              "baseline_report_sha256": digest(args.baseline), "candidate_report_sha256": digest(args.candidate),
              "protocol_sha256": digest(args.protocol),
              "baseline_matches_published_binary": base["matches_published_binary"],
              "baseline": a, "candidate": b, "deltas": {key: b[key] - a[key] for key in keys},
              "weight_copy_delta_bytes": b["blocks"]["weights"]["bytes"] - a["blocks"]["weights"]["bytes"],
              "scope": "Measured compressor plus decoder prefix plus archive-side weights. Full payload, compressed dictionary, archive footer and invocation arguments are excluded; no full prize score or runtime claim."}
    with args.output.open("x") as file:
        json.dump(report, file, indent=2)
        file.write("\n")
    print(json.dumps(report["deltas"], indent=2))


if __name__ == "__main__":
    main()
