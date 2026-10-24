#!/usr/bin/env python3
"""Compare complete Linux release components for baseline, prior and blend."""
import argparse
import json
from pathlib import Path

from make_samples import digest
from package_structure import inspect

NAMES = ("baseline", "prior", "blend")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (*NAMES, "protocol", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    records = {name: json.loads(getattr(args, name).read_text()) for name in NAMES}
    base, prior, blend = (records[name] for name in NAMES)
    if any(not row["passed"] or row.get("weight_binding") or row.get("metadata_binding")
           for row in records.values()):
        raise ValueError("all release packer checks must pass without altered external weights or metadata")
    if (base.get("bit_weight_binding") or base.get("bit_blend_binding")
            or prior.get("bit_blend_binding") or blend.get("bit_weight_binding")):
        raise ValueError("release variants were mixed")
    previous, selected = prior.get("bit_weight_binding"), blend.get("bit_blend_binding")
    if (not previous or not selected
            or previous["name"] != protocol["prior_variant"]
            or previous["model_sha256"] != protocol["prior_model_sha256"]
            or previous["recipe_sha256"] != protocol["prior_recipe_sha256"]
            or selected["name"] != protocol["blend_variant"]
            or selected["model_sha256"] != protocol["blend_model_sha256"]
            or selected["recipe_sha256"] != protocol["blend_recipe_sha256"]):
        raise ValueError("model binding differs from frozen protocol")
    expected = {"changed": ["src/bit_head_weights.h"], "missing": [], "added": []}
    if (base["source_changes"] != {"changed": [], "missing": [], "added": []}
            or prior["source_changes"] != expected or blend["source_changes"] != expected):
        raise ValueError("uncontrolled source changes")
    for key in ("upstream_commit", "compiler", "linker", "packages", "platform", "cpu", "compiler_driver"):
        if len({json.dumps(row[key], sort_keys=True) for row in records.values()}) != 1:
            raise ValueError("uncontrolled release environment: " + key)
    for name, row in records.items():
        folder = getattr(args, name).parent
        actual, decoder = inspect((folder / "comp9").read_bytes())
        if (digest(folder / "comp9") != row["package"]["compressor_sha256"]
                or actual != row["package"] or (folder / "decoder-prefix").read_bytes() != decoder):
            raise ValueError("release binary or decoder prefix differs from saved record: " + name)
        if name != "baseline":
            binding = previous if name == "prior" else selected
            if (binding["before_sha256"] != base["source_files"]["src/bit_head_weights.h"]["sha256"]
                    or binding["after_sha256"] != row["source_files"]["src/bit_head_weights.h"]["sha256"]):
                raise ValueError("embedded bit-model source hash differs: " + name)
    if (not base["matches_published_binary"]
            or base["package"]["compressor_sha256"] != protocol["baseline_comp9_sha256"]
            or prior["package"]["compressor_sha256"] != protocol["prior_comp9_sha256"]):
        raise ValueError("baseline or prior package did not reproduce its pinned release hash")
    a, b, c = (row["package"] for row in (base, prior, blend))
    if any(a["blocks"][key] != row["blocks"][key] for key in ("weights", "hints", "order")
           for row in (b, c)):
        raise ValueError("non-bit-model release block changed")
    keys = ("compressor_bytes", "packed_program_bytes", "decoder_prefix_bytes",
            "component_bytes_excluding_dictionary_payload_footer_args")
    result = {"kind": "bit-blend-release-component-comparison", "version": 1,
              "protocol_sha256": digest(args.protocol),
              "report_sha256": {name: digest(getattr(args, name)) for name in NAMES},
              "packages": {name: row["package"] for name, row in records.items()},
              "deltas_vs_prior": {key: c[key] - b[key] for key in keys},
              "deltas_vs_baseline": {key: c[key] - a[key] for key in keys},
              "scope": "Release executable, decoder prefix and external weight blocks; payload, dictionary, footer and arguments excluded. No full enwik9 score or resource claim."}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"vs_prior": result["deltas_vs_prior"], "vs_baseline": result["deltas_vs_baseline"]}, indent=2))


if __name__ == "__main__":
    main()
