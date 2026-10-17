#!/usr/bin/env python3
"""Build and benchmark the original x86 kernels directly on Linux, without Docker."""
import argparse
import datetime
import json
from pathlib import Path
import platform
import shutil
import subprocess

from benchmark import capture
from cmix_fixture_support import instrument_fixture, provenance
from cmix_parity_support import SUPPORT, instrument
from cmix_variants import VARIANTS, apply_variant
from cmix_preprocess_support import apply_portable_preprocessing
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
import native_cmix

ROOT = Path(__file__).resolve().parents[1]


def build(args):
    upstream = json.loads(MANIFEST.read_text())
    if any(differences(upstream["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream source differs")
    out = args.output.resolve()
    if out.is_relative_to(ENGINE) or out.is_relative_to(native_cmix.PORT):
        raise ValueError("build output must be outside source trees")
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    shutil.copytree(ENGINE, source)
    shutil.copyfile(native_cmix.PORT / "overlay/src/native_corpus.h", source / "src/native_corpus.h")
    with (SUPPORT / "corpus.patch").open("rb") as patch:
        subprocess.run(["patch", "-p1", "--batch", "--fuzz=0"], cwd=source, stdin=patch, check=True)
    variant = apply_variant(source, args.variant)
    preprocessing_support = apply_portable_preprocessing(source)
    instrument_fixture(source)
    instrument(source, portable_random=False)
    command = ["make", f"-j{args.jobs}", "CC=clang++-18", "prof_use"]
    metadata = {
        "kind": "native-linux-development-build", "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "upstream_commit": upstream["commit"], "simde_commit": None,
        "platform": platform.platform(), "machine": platform.machine(), "cpu": native_cmix.cpu_name(),
        "compiler": capture("clang++-18", "--version"), "command": command,
        "linker": capture("ld.lld-18", "--version"), "libc": capture("ldd", "--version"),
        "fixture_support": provenance(), "model_variant": variant,
        "preprocessing_support": preprocessing_support,
        "initialization": "original Linux libc generator", "source_files": inventory(source),
        "support_files": inventory(SUPPORT), "script_sha256": digest(Path(__file__)),
        "scope": "Original x86 kernels, paging and upstream PGO/LTO flags. Development phases and declared model variant; no submission packaging or published-binary equivalence claim.",
    }
    native_cmix.write_json(out / "build.json", metadata)
    with (out / "build.log").open("wb") as log:
        result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
    metadata["exit_code"] = result.returncode
    native_cmix.write_json(out / "build.json", metadata)
    result.check_returncode()
    metadata.update(binary_sha256=digest(source / "cmix"), binary_bytes=(source / "cmix").stat().st_size)
    helper = ["clang++-18", "-O2", "-std=c++17", "-Isrc", str(native_cmix.PORT / "prepare_sample.cpp"),
              "-o", str(out / "prepare-sample")]
    with (out / "prepare-build.log").open("wb") as log:
        subprocess.run(helper, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
    metadata["sample_helper"] = {"command": helper, "sha256": digest(out / "prepare-sample")}
    native_cmix.write_json(out / "build.json", metadata)
    print("Built", source / "cmix", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("build")
    compile_parser.add_argument("--output", type=Path, required=True)
    compile_parser.add_argument("--jobs", type=int, default=2)
    compile_parser.add_argument("--variant", choices=VARIANTS, default="baseline")
    bench = sub.add_parser("bench")
    bench.add_argument("inputs", type=Path, nargs="+")
    for name in ("build", "manifest", "output"):
        bench.add_argument("--" + name, type=Path, required=True)
    bench.add_argument("--timeout", type=float, default=1800)
    bench.set_defaults(repeats=1, record=None, note="")
    args = parser.parse_args()
    if (platform.system(), platform.machine()) != ("Linux", "x86_64"):
        parser.error("requires native Linux x86-64")
    if getattr(args, "jobs", 1) < 1 or getattr(args, "timeout", 1) <= 0:
        parser.error("jobs and timeout must be positive")
    try:
        if args.command == "build":
            build(args)
            return 0
        # Reuse the exact round-trip/context checks and platform-aware timer.
        native_cmix.CODEC = "cmix-neif-linux-x86-dict"
        return native_cmix.bench(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
