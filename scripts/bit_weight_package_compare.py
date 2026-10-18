#!/usr/bin/env python3
"""Compare complete release components for one embedded bit-model change."""
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
    p = json.loads(args.protocol.read_text())
    base, cand = (json.loads(path.read_text()) for path in (args.baseline, args.candidate))
    if (not base["passed"] or not cand["passed"] or base.get("weight_binding")
            or base.get("bit_weight_binding") or cand.get("weight_binding")):
        raise ValueError("requires passing unchanged baseline and only the trained bit model")
    binding = cand.get("bit_weight_binding")
    if (not binding or binding["name"] != p["variant"]
            or binding["model_sha256"] != p["model_sha256"]
            or binding["recipe_sha256"] != p["recipe_sha256"]):
        raise ValueError("candidate bit model differs from frozen protocol")
    if (base["source_changes"] != {"changed": [], "missing": [], "added": []}
            or cand["source_changes"] != {"changed": ["src/bit_head_weights.h"], "missing": [], "added": []}):
        raise ValueError("uncontrolled source changes")
    for key in ("upstream_commit", "compiler", "linker", "packages", "platform", "cpu", "compiler_driver"):
        if base[key] != cand[key]:
            raise ValueError("uncontrolled release environment: " + key)
    for record, path in ((base, args.baseline), (cand, args.candidate)):
        folder = path.parent
        data = (folder / "comp9").read_bytes()
        actual, decoder = inspect(data)
        if (digest(folder / "comp9") != record["package"]["compressor_sha256"]
                or actual != record["package"] or (folder / "decoder-prefix").read_bytes() != decoder):
            raise ValueError("package record or decoder prefix differs from saved bytes")
    a, b = base["package"], cand["package"]
    if not base["matches_published_binary"] or a["compressor_sha256"] != p["baseline_comp9_sha256"]:
        raise ValueError("baseline release does not reproduce the published package")
    if any(a["blocks"][key] != b["blocks"][key] for key in ("weights", "hints", "order")):
        raise ValueError("a non-bit-model release block changed")
    keys = ("compressor_bytes", "packed_program_bytes", "decoder_prefix_bytes",
            "component_bytes_excluding_dictionary_payload_footer_args")
    result = {"kind": "bit-model-release-component-comparison", "version": 1,
              "protocol_sha256": digest(args.protocol),
              "baseline_report_sha256": digest(args.baseline),
              "candidate_report_sha256": digest(args.candidate),
              "baseline": a, "candidate": b,
              "deltas": {key: b[key]-a[key] for key in keys},
              "scope": "Complete release executable plus decoder-prefix and duplicated external weight block; payload, dictionary, footer and arguments excluded. No full prize score or resource claim."}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["deltas"], indent=2))


if __name__ == "__main__":
    main()
