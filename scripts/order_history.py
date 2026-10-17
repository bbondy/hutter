#!/usr/bin/env python3
"""Verify and retain identical-content comparisons with different article orders."""
import argparse
import bz2
import datetime
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import tempfile
import zlib

from article_order import VARIANTS, pages_from_bytes, restore_source, sha
from make_samples import digest
from cmix_fixture_support import corpus_arguments, context_report, validate_context

ROOT = Path(__file__).resolve().parents[1] / "benchmarks/article-order"


def same_setup(metadata):
    """Input hashes may differ; the model, assets and runner may not."""
    keys = ("binary_sha256", "side_data", "build", "native_arguments", "runner_sha256",
            "platform", "machine")
    if not metadata or any(any(k not in m for k in keys) for m in metadata):
        raise ValueError("incomplete model provenance")
    if any(any(m.get(k) != metadata[0].get(k) for k in keys) for m in metadata[1:]):
        raise ValueError("runs differ in model/build/assets/page count/runner/platform")


def checked_restoration(raw, sample, manifest):
    if sha(raw) != sample["ordered_raw_sha256"]:
        raise ValueError("inverse preprocessing differs from the ordered raw input")
    pages = pages_from_bytes(raw)
    if [p["id"] for p in pages] != sample["page_ids"]:
        raise ValueError("decoded page order differs from manifest")
    page_set = sha("\n".join(sorted(sha(p["raw"]) for p in pages)).encode())
    if len(pages) != manifest["page_count"] or page_set != manifest["page_set_sha256"]:
        raise ValueError("decoded article set differs from manifest")
    restored = restore_source(raw)
    if len(restored) != manifest["raw_bytes"] or sha(restored) != manifest["raw_sha256"]:
        raise ValueError("source-order restoration failed")
    return sha(restored)


def summarize(args):
    manifest = json.loads(args.manifest.read_text())
    samples = {s["variant"]: s for s in manifest["samples"]}
    names = manifest.get("variant_names", list(VARIANTS))
    baseline_name = manifest.get("baseline_variant", "source")
    if len(names) != len(set(names)) or set(samples) != set(names) or baseline_name not in names:
        raise ValueError("manifest variants or baseline are incomplete")
    helper = args.build.resolve() / "prepare-sample"
    if digest(helper) != manifest["helper_sha256"]:
        raise ValueError("preprocessor hash differs from fixture")
    metadata = [json.loads((p / "metadata.json").read_text()) for p in args.runs]
    same_setup(metadata)
    if metadata[0]["native_arguments"] != corpus_arguments(manifest, metadata[0]["build"]):
        raise ValueError("native article count differs from fixture")
    if metadata[0]["build"]["upstream_commit"] != manifest["upstream_commit"]:
        raise ValueError("model and preprocessor upstream differ")
    variants, logs = {}, []
    with tempfile.TemporaryDirectory(prefix="hutter-order-verify-") as tmp:
        for run, meta in zip(args.runs, metadata):
            if digest(run / "cmix") != meta["binary_sha256"]:
                raise ValueError("local runner binary has changed")
            for line in (run / "results.jsonl").read_text().splitlines():
                row = json.loads(line)
                name = Path(row["input"]).stem
                if name not in samples or name in variants:
                    raise ValueError("expected one trial per distinct variant")
                sample = samples[name]
                if (row["input_sha256"], row["input_bytes"]) != (sample["sha256"], sample["bytes"]):
                    raise ValueError("result input does not match variant")
                if not row["roundtrip"] or not row.get("repeat_matches", True):
                    raise ValueError("trial failed; retain failed native run, do not report a gain")
                if any(row[phase]["status"] != "ok" for phase in ("compress", "decompress")):
                    raise ValueError("trial phase did not succeed")
                archive = Path(row["compress"]["command"][-1])
                restored = Path(row["decompress"]["command"][-1])
                if digest(archive) != row["archive_sha256"] or archive.stat().st_size != row["archive_bytes"]:
                    raise ValueError("archive differs from saved trial")
                if digest(restored) != sample["sha256"]:
                    raise ValueError("decoder output differs from prepared input")
                for asset, info in meta["side_data"].items():
                    path = restored.parent / ("dictionary.dic" if asset == "dictionary/english.dic" else asset)
                    if digest(path) != info["sha256"] or path.stat().st_size != info["bytes"]:
                        raise ValueError("trial asset differs from recorded build")
                raw = Path(tmp) / f"{name}.xml"
                subprocess.run([str(helper), *manifest.get("helper_arguments", []), "decode", str(restored), str(raw)], check=True)
                final_sha = checked_restoration(raw.read_bytes(), sample, manifest)
                log_hashes = {}
                for phase in ("compress", "decompress"):
                    log = Path(row[phase]["log"])
                    log_hashes[phase] = digest(log)
                    logs.append((log, f"{name}-{phase}.log"))
                context = {}
                if "redirect_prefix_count" in manifest:
                    context = {phase: context_report(Path(row[phase]["log"])) for phase in ("compress", "decompress")}
                    validate_context(context["compress"], context["decompress"], manifest)
                    if manifest["redirect_prefix_count"] < manifest["page_count"]:
                        if any("entering main text block" not in Path(row[phase]["log"]).read_text(errors="replace")
                               for phase in ("compress", "decompress")):
                            raise ValueError("main text phase was not observed")
                variants[name] = {
                    "context": context,
                    "payload_bytes": row["archive_bytes"], "archive_sha256": row["archive_sha256"],
                    "prepared_bytes": row["input_bytes"], "prepared_sha256": row["input_sha256"],
                    "order_side_information_bytes": manifest["order_side_information_bytes"],
                    "restored_raw_sha256": final_sha, "original_bytes_roundtrip": True,
                    "compress_seconds": row["compress"]["wall_seconds"],
                    "decompress_seconds": row["decompress"]["wall_seconds"],
                    "peak_rss_bytes": max(row[p]["peak_rss_bytes"] or 0 for p in ("compress", "decompress")),
                    "source_run": str(run.resolve()), "source_metadata_sha256": digest(run / "metadata.json"),
                    "source_results_sha256": digest(run / "results.jsonl"), "log_sha256": log_hashes,
                    "graph": manifest["graph"]["variants"][name],
                }
    if set(variants) != set(names):
        raise ValueError("all declared variants need verified results")
    baseline = variants[baseline_name]["payload_bytes"]
    for result in variants.values():
        result["delta_bytes_vs_baseline"] = result["payload_bytes"] - baseline
        result["delta_percent_vs_baseline"] = 100 * result["delta_bytes_vs_baseline"] / baseline
        if baseline_name == "source":
            result["delta_bytes_vs_source"] = result["delta_bytes_vs_baseline"]
            result["delta_percent_vs_source"] = result["delta_percent_vs_baseline"]
    report = {
        "version": 1, "kind": "article-order-comparison", "role": manifest["role"],
        "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "manifest_sha256": digest(args.manifest), "page_set_sha256": manifest["page_set_sha256"],
        "raw_sha256": manifest["raw_sha256"], "raw_bytes": manifest["raw_bytes"],
        "page_count": manifest["page_count"], "binary_sha256": metadata[0]["binary_sha256"],
        "side_data": metadata[0]["side_data"], "verifier_sha256": digest(Path(__file__)),
        "restoration_code_sha256": digest(Path(__file__).with_name("article_order.py")),
        "size_scope": manifest["size_scope"], "baseline": manifest["baseline"],
        "timing_scope": "single trials, potentially concurrent; not a performance benchmark",
        "baseline_variant": baseline_name, "variant_names": names,
        "native_arguments": metadata[0]["native_arguments"],
        "development_header_bytes": manifest.get("development_header_bytes", 0),
        "variants": variants,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.manifest, args.output / "manifest.json")
    for source, name in logs:
        shutil.copyfile(source, args.output / name)
    for run in args.runs:
        dest = args.output / run.name
        dest.mkdir()
        for name in ("metadata.json", "results.jsonl"):
            shutil.copyfile(run / name, dest / name)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print_table(report, args.output.name)


def standard(args):
    """Cheap codec controls on the same prepared inputs; no model-gain inference."""
    manifest = json.loads(args.manifest.read_text())
    results = []
    for sample in manifest["samples"]:
        data = Path(sample["path"]).read_bytes()
        if sha(data) != sample["sha256"]:
            raise ValueError("fixture hash differs")
        for name, encode, decode in (
            ("zlib-9", lambda d: zlib.compress(d, 9), zlib.decompress),
            ("bzip2-9", lambda d: bz2.compress(d, 9), bz2.decompress),
            ("xz-9", lambda d: lzma.compress(d, preset=9), lzma.decompress),
        ):
            archive = encode(data)
            if decode(archive) != data:
                raise ValueError(f"{name} roundtrip failed")
            results.append({"codec": name, "variant": sample["variant"], "input_sha256": sha(data),
                            "archive_bytes": len(archive), "archive_sha256": sha(archive),
                            "prepared_roundtrip": True})
    import platform
    report = {"version": 1, "kind": "article-order-standard-controls", "role": manifest["role"],
              "manifest_sha256": digest(args.manifest), "script_sha256": digest(Path(__file__)),
              "python": platform.python_version(), "platform": platform.platform(),
              "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
              "library_modules_sha256": {m.__name__: digest(Path(m.__file__))
                                         for m in (__import__("_bz2"), __import__("_lzma"), zlib)},
              "scope": "Prepared-stream codec payload controls; not a cmix or prize score", "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    for row in results:
        print(f"{row['codec']:8} {row['variant']:6} {row['archive_bytes']:8}")


def print_table(report, name):
    print(f"{name}: {report['page_count']} pages, {report['raw_bytes']} raw bytes; payload only")
    print("Order      Bytes      Delta    Delta %   Exact original")
    for name in report.get("variant_names", list(VARIANTS)):
        r = report["variants"][name]
        delta = r.get("delta_bytes_vs_baseline", r.get("delta_bytes_vs_source"))
        pct = r.get("delta_percent_vs_baseline", r.get("delta_percent_vs_source"))
        print(f"{name:12} {r['payload_bytes']:8} {delta:+10} {pct:+9.3f}   {r['original_bytes_roundtrip']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    summary = sub.add_parser("summarize")
    summary.add_argument("--manifest", required=True, type=Path)
    summary.add_argument("--build", required=True, type=Path)
    summary.add_argument("--runs", required=True, type=Path, nargs="+")
    summary.add_argument("--output", required=True, type=Path)
    listing = sub.add_parser("list")
    listing.add_argument("--root", type=Path, default=ROOT)
    controls = sub.add_parser("standard")
    controls.add_argument("--manifest", required=True, type=Path)
    controls.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "list":
            for path in sorted(args.root.glob("*/report.json")):
                report = json.loads(path.read_text())
                if report["kind"] == "article-order-comparison":
                    print_table(report, path.parent.name)
        else:
            {"standard": standard, "summarize": summarize}[args.command](args)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
