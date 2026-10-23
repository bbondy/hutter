#!/usr/bin/env python3
"""Compare full release components for isolated E1 against the exact baseline."""
import argparse
import json
from pathlib import Path

from cmix_metadata_release_support import ADDED, CHANGED, PORT, UPSTREAM_COMMIT
from make_samples import digest
from package_structure import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "protocol", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    base, candidate = (json.loads(path.read_text()) for path in (args.baseline, args.candidate))
    if (not base["passed"] or not candidate["passed"] or base.get("weight_binding")
            or base.get("bit_weight_binding") or base.get("metadata_binding")
            or candidate.get("weight_binding") or candidate.get("bit_weight_binding")):
        raise ValueError("requires passing unchanged baseline and E1-only candidate")
    binding = candidate.get("metadata_binding")
    if (not binding or binding["name"] != protocol["variant"]
            or binding["origin_commit"] != protocol["origin_commit"]
            or binding["origin_commit"] != UPSTREAM_COMMIT
            or binding["recipe_sha256"] != protocol["recipe_sha256"]
            or binding["patch_sha256"] != protocol["patch_sha256"]
            or binding["patch_sha256"] != digest(PORT / "e1.patch")):
        raise ValueError("E1 patch differs from frozen protocol")
    if (base["source_changes"] != {"changed": [], "missing": [], "added": []}
            or candidate["source_changes"] != {"changed": list(CHANGED), "missing": [], "added": list(ADDED)}):
        raise ValueError("uncontrolled release source changes")
    for name in CHANGED:
        if (binding["before_sha256"][name] != base["source_files"][name]["sha256"]
                or binding["after_sha256"][name] != candidate["source_files"][name]["sha256"]):
            raise ValueError("E1 changed source hash differs from release report")
    for name in ADDED:
        if (binding["new_headers_sha256"][name] != digest(PORT / Path(name).name)
                or binding["new_headers_sha256"][name] != candidate["source_files"][name]["sha256"]):
            raise ValueError("E1 new header differs from frozen source")
    for key in ("upstream_commit", "compiler", "linker", "packages", "platform", "cpu", "compiler_driver"):
        if base[key] != candidate[key]:
            raise ValueError("uncontrolled release environment: " + key)
    for record, path in ((base, args.baseline), (candidate, args.candidate)):
        folder = path.parent
        package, decoder = inspect((folder / "comp9").read_bytes())
        if (digest(folder / "comp9") != record["package"]["compressor_sha256"]
                or package != record["package"] or (folder / "decoder-prefix").read_bytes() != decoder):
            raise ValueError("release binary or decoder prefix differs from saved record")
    a, b = base["package"], candidate["package"]
    if not base["matches_published_binary"] or a["compressor_sha256"] != protocol["baseline_comp9_sha256"]:
        raise ValueError("baseline does not reproduce the published comp9")
    if any(a["blocks"][key] != b["blocks"][key] for key in ("weights", "hints", "order")):
        raise ValueError("external release data blocks changed")
    keys = ("compressor_bytes", "packed_program_bytes", "decoder_prefix_bytes",
            "component_bytes_excluding_dictionary_payload_footer_args")
    result = {"kind": "e1-metadata-release-component-comparison", "version": 1,
              "protocol_sha256": digest(args.protocol),
              "baseline_report_sha256": digest(args.baseline),
              "candidate_report_sha256": digest(args.candidate),
              "baseline": a, "candidate": b,
              "deltas": {key: b[key] - a[key] for key in keys},
              "scope": "Exact Linux release executable, decoder prefix and external blocks; payload, dictionary, footer and arguments excluded. This is package accounting, not a full prize score."}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["deltas"], indent=2))


if __name__ == "__main__":
    main()
