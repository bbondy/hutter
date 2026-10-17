#!/usr/bin/env python3
"""Reproduce upstream's full training/coder stream with its preparation-only mode."""
import argparse
import datetime
import json
from pathlib import Path
import platform
import shutil
import subprocess

from benchmark import capture, measured
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
from native_cmix import PORT, SIMDE_COMMIT, write_json

ROOT = Path(__file__).resolve().parents[1]
PATCH = ENGINE / "training/tf/1_dump/trainmodes.patch"
EXPECTED = {
    "archive.cmix.temp": (552750198, "8e0b264a777cb56a6be48c58002450c4711b1cebf3ffcb0129a32ef34273c3ba"),
    "archive.cmix.temp.vorpack": (555771398, "e556d3f837c66c69e0a4f3a1e972b05bdb034633f6a8cadd6d91ef9c34135111"),
}


def run(args):
    upstream = json.loads(MANIFEST.read_text())
    if any(differences(upstream["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream differs")
    corpus = args.enwik9.resolve()
    if corpus.stat().st_size != 1000000000 or digest(corpus, "sha1") != "2996e86fb978f93cca8f566cc56998923e7fe581":
        raise ValueError("requires verified official enwik9")
    darwin = platform.system() == "Darwin"
    if darwin:
        simde = args.native.resolve() / "simde"
        if capture("git", "-C", str(simde), "rev-parse", "HEAD") != SIMDE_COMMIT:
            raise ValueError("SIMDe revision differs")
        if capture("git", "-C", str(simde), "status", "--porcelain"):
            raise ValueError("SIMDe source is modified")
    out = args.output.resolve()
    if out.is_relative_to(ENGINE) or out.is_relative_to(PORT):
        raise ValueError("output must be outside the source/port trees")
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    shutil.copytree(ENGINE, source)
    # TRAIN_MODE adds an include beside this Mac hunk. Update context only,
    # keeping the actual allocator-header replacement and zero-fuzz application.
    if darwin:
        (out / "simde").symlink_to(simde, target_is_directory=True)
        port_patch = (PORT / "port.patch").read_text()
        context = '@@ -18,7 +18,7 @@\n #include "../ppmd_prewarm.h"\n'
        if port_patch.count(context) != 1:
            raise ValueError("expected PPMd port context changed")
        port_patch = port_patch.replace(context,
            '@@ -18,8 +18,8 @@\n #include "../ppmd_prewarm.h"\n #include "../train_mode.h"\n')
        (out / "native-training.patch").write_text(port_patch)
    with (out / "patch.log").open("wb") as log:
        with PATCH.open("rb") as patch:
            subprocess.run(["patch", "-p1", "--batch", "--fuzz=0"], cwd=source, stdin=patch,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        if darwin:
            shutil.copytree(PORT / "overlay", source, dirs_exist_ok=True)
            with (out / "native-training.patch").open("rb") as patch:
                subprocess.run(["patch", "-p1", "--batch", "--fuzz=0"], cwd=source, stdin=patch,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
    compiler = "clang++" if darwin else "clang++-18"
    cc = "CC=" + compiler + " -DTRAIN_MODE=1" + (" -Isrc -I../simde" if darwin else "")
    command = ["make", f"-j{args.jobs}", cc, "cmix"]
    report = {
        "kind": "native-full-coder-stream", "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "script_sha256": digest(Path(__file__)), "upstream_commit": upstream["commit"],
        "training_patch_sha256": digest(PATCH), "port_files": inventory(PORT) if darwin else {},
        "adapted_port_patch_sha256": digest(out / "native-training.patch") if darwin else None,
        "source_files": inventory(source), "simde_commit": SIMDE_COMMIT if darwin else None,
        "platform": platform.platform(), "compiler": capture(compiler, "--version"),
        "build_command": command, "input_bytes": corpus.stat().st_size, "input_sha256": digest(corpus),
        "scope": "Upstream TRAIN_MODE=1 preparation only; no learned predictions, archive, or prize score. Concurrent timing is exploratory.",
    }
    write_json(out / "report.json", report)
    with (out / "build.log").open("wb") as log:
        result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
    report["build_exit_code"] = result.returncode
    write_json(out / "report.json", report)
    result.check_returncode()
    binary = source / "cmix"
    report["binary_sha256"] = digest(binary)
    work = out / "run"
    work.mkdir()
    report["assets"] = {}
    for origin, name in ((ENGINE / "dictionary/english.dic", ".dict"),
                         (ENGINE / "src/readalike_prepr/data/new_article_order", ".new_article_order")):
        shutil.copyfile(origin, work / name)
        report["assets"][name] = {"bytes": origin.stat().st_size, "sha256": digest(origin)}
    import os
    os.chdir(work)
    report["execution"] = measured([str(binary), "-e", str(corpus), "archive"], out / "prepare.log", args.timeout)
    report["outputs"] = {}
    for name, (size, sha) in EXPECTED.items():
        path = work / name
        if path.exists():
            report["outputs"][name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
            report["outputs"][name]["matches_upstream"] = (path.stat().st_size, digest(path)) == (size, sha)
    report["passed"] = (report["execution"]["status"] == "ok" and len(report["outputs"]) == len(EXPECTED)
                        and all(r["matches_upstream"] for r in report["outputs"].values()))
    report["log_sha256"] = digest(out / "prepare.log")
    report["stages"] = {name: {"bytes": (work / name).stat().st_size, "sha256": digest(work / name)}
                        for name in (".main_reordered", ".main_phda9prepr", ".ready4cmix")
                        if (work / name).exists()}
    write_json(out / "report.json", report)
    print(json.dumps({"passed": report["passed"], "outputs": report["outputs"]}, indent=2))
    return 0 if report["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("enwik9", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--native", type=Path, help="existing native Mac build providing pinned SIMDe")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    if (platform.system(), platform.machine()) not in (("Darwin", "arm64"), ("Linux", "x86_64")):
        parser.error("requires native Apple Silicon or Linux x86-64")
    if platform.system() == "Darwin" and not args.native:
        parser.error("Mac preparation requires --native for its pinned SIMDe source")
    if args.jobs < 1 or args.timeout <= 0:
        parser.error("jobs and timeout must be positive")
    try:
        return run(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
