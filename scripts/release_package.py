#!/usr/bin/env python3
"""Build the real Linux release package and measure its executable components."""
import argparse
import datetime
import json
from pathlib import Path
import platform
import shutil
import subprocess

from benchmark import capture, measured
from cmix_bit_weight_support import VARIANT as BIT_WEIGHT_VARIANT, apply as apply_bit_weight
from cmix_metadata_release_support import VARIANT as METADATA_E1_VARIANT, CHANGED as METADATA_CHANGED, ADDED as METADATA_ADDED, apply as apply_metadata_e1
from cmix_weight_support import WEIGHTS, apply_container
from competitive import ENGINE, MANIFEST, differences, inventory, problems
from make_samples import digest
from package_structure import inspect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--weight-container", type=Path)
    parser.add_argument("--bit-weight-variant", choices=(BIT_WEIGHT_VARIANT,))
    parser.add_argument("--metadata-e1-variant", choices=(METADATA_E1_VARIANT,))
    parser.add_argument("--timeout", type=float, default=7200)
    args = parser.parse_args()
    if sum(bool(x) for x in (args.weight_container, args.bit_weight_variant, args.metadata_e1_variant)) > 1:
        parser.error("change only one model or metadata component at a time")
    errors = problems()
    if errors:
        raise ValueError("; ".join(errors))
    upstream = json.loads(MANIFEST.read_text())
    if any(differences(upstream["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned source differs")
    output = args.output.resolve()
    if output.is_relative_to(ENGINE):
        raise ValueError("output must be outside the source tree")
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    shutil.copytree(ENGINE, source)
    binding = apply_container(source, args.weight_container) if args.weight_container else None
    bit_binding = apply_bit_weight(source, args.bit_weight_variant) if args.bit_weight_variant else None
    metadata_binding = apply_metadata_e1(source, args.metadata_e1_variant) if args.metadata_e1_variant else None
    files = inventory(source)
    delta = differences(upstream["files"], files)
    expected = ["src/transformer.h", WEIGHTS] if binding else (["src/bit_head_weights.h"] if bit_binding else list(METADATA_CHANGED) if metadata_binding else [])
    added = list(METADATA_ADDED) if metadata_binding else []
    if delta != {"changed": sorted(expected), "missing": [], "added": sorted(added)}:
        raise ValueError("release copy has uncontrolled changes")
    # A hosted image can contain additional GCC versions. Clang selects their
    # headers even when the clang package itself matches the reference version.
    driver = subprocess.run(["clang++-18", "-v", "-E", "-x", "c++", "/dev/null"],
                            capture_output=True, text=True, check=True).stderr
    report = {"kind": "native-linux-release-package", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
              "script_sha256": digest(Path(__file__)),
              "structure_parser_sha256": digest(ROOT / "scripts/package_structure.py"),
              "upstream_commit": upstream["commit"], "source_files": files,
              "source_changes": delta, "weight_binding": binding, "bit_weight_binding": bit_binding,
              "metadata_binding": metadata_binding,
              "platform": platform.platform(), "cpu": capture("lscpu"),
              "compiler": capture("clang++-18", "--version"), "linker": capture("ld.lld-18", "--version"),
              "compiler_driver": driver,
              "packages": capture("dpkg-query", "-W", "-f=${Package}=${Version}\n"),
              "scope": "Unmodified upstream release build/packer and guards; optional explicit single-model change. Executable components only, no full enwik9 score or resource eligibility."}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    import os
    previous = Path.cwd()
    try:
        os.chdir(output)
        report["execution"] = measured(["bash", str(source / "build.sh")], output / "stderr.log",
                                       args.timeout, output=output / "build.log")
    finally:
        os.chdir(previous)
    save()
    if report["execution"]["status"] != "ok" or not (output / "comp9").exists():
        return 1
    structure, decoder = inspect((output / "comp9").read_bytes())
    if structure["blocks"]["weights"]["sha256"] != digest(source / WEIGHTS):
        raise ValueError("packaged weights differ from the bound input")
    checks = ("CUT-Gegenprobe voll: bitidentisch", "CUT-Gegenprobe dec: Praefix bitidentisch",
              "CUT-Stubprobe voll: bitidentisch", "CUT-Stubprobe dec: Praefix bitidentisch")
    log = (output / "build.log").read_text(errors="replace")
    report["packer_checks"] = {check: check in log for check in checks}
    report["package"] = structure
    report["matches_published_binary"] = structure["compressor_sha256"] == upstream["expected_comp9_sha256"]
    report["log_sha256"] = {name: digest(output / name) for name in ("build.log", "stderr.log")}
    report["passed"] = all(report["packer_checks"].values())
    (output / "decoder-prefix").write_bytes(decoder)
    save()
    print(json.dumps({"passed": report["passed"], "matches_published_binary": report["matches_published_binary"],
                      "package": structure}, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
