#!/usr/bin/env python3
"""Verify fixed-input model ablations through original-byte restoration."""
import argparse
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from cmix_fixture_support import context_report, corpus_arguments, validate_context
from cmix_variants import model_identity, recipe
import cmix_retrieval_support as retrieval
import cmix_alias_support as alias
import cmix_activity_support as activity
import cmix_bit_trace_support as bit_trace
import cmix_bit_weight_support as bit_weight
import cmix_metadata_support as metadata_support
from make_samples import digest
from order_history import checked_restoration

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECIPES = {"retrieval_variant": (retrieval, "retrieval-"), "alias_variant": (alias, "alias-"),
                  "activity_variant": (activity, "activity-"), "bit_trace_variant": (bit_trace, "bit-trace-"),
                  "bit_weight_variant": (bit_weight, "bit-weight-"),
                  "metadata_variant": (metadata_support, "metadata-")}


def source_recipe(build):
    selected = [key for key in SOURCE_RECIPES if build.get(key)]
    if len(selected) > 1:
        raise ValueError("only one source-code recipe may change per experiment")
    return selected[0] if selected else None


def model_name(build):
    key = source_recipe(build)
    if key:
        model_identity({**build, key: None})
        return SOURCE_RECIPES[key][1] + build[key]["name"]
    return model_identity(build)[0]


def compatible_builds(baseline, candidate, baseline_source=None):
    if model_identity(baseline)[0] != "baseline":
        raise ValueError("comparison requires the unchanged baseline model")
    name = model_name(candidate)
    key = source_recipe(candidate)
    if key:
        module, _ = SOURCE_RECIPES[key]
        change = candidate[key]
        if baseline_source is None:
            raise ValueError("source-code comparison requires the baseline source file")
        if baseline.get("weight_binding") or candidate.get("weight_binding"):
            raise ValueError("source-code comparison requires original weights")
        if model_identity({**candidate, key: None})[0] != "baseline":
            raise ValueError("source-code comparison changes model parameters")
        if key == "metadata_variant":
            if change["recipe_sha256"] != digest(Path(module.__file__)):
                raise ValueError("metadata recipe differs from built source")
            if change["origin_commit"] != module.UPSTREAM_COMMIT or change["before_sha256"] != module.BEFORE:
                raise ValueError("metadata origin or frozen patch base differs")
            with tempfile.TemporaryDirectory(prefix="hutter-metadata-verify-") as tmp:
                target = Path(tmp) / "src"
                target.mkdir()
                for source_file in module.BEFORE:
                    shutil.copyfile(baseline_source / source_file, Path(tmp) / source_file)
                expected_change = module.apply(Path(tmp), change["name"])
                for field in ("patch_sha256", "original_upstream_patch_sha256", "after_sha256", "new_headers_sha256"):
                    if expected_change[field] != change[field]:
                        raise ValueError("metadata patch differs from measured candidate")
                changed = set(module.BEFORE) | {"src/b1_interp.h", "src/neif_levers.h"}
                for source_file in changed:
                    if candidate["source_files"][source_file]["sha256"] != digest(Path(tmp) / source_file):
                        raise ValueError("candidate metadata source differs from frozen patch")
            if any(baseline["source_files"][source_file]["sha256"] != module.BEFORE[source_file]
                   for source_file in module.BEFORE):
                raise ValueError("metadata baseline headers changed")
        else:
            path = baseline_source / module.SOURCE
            if change["source_file"] != module.SOURCE or digest(path) != change["before_sha256"]:
                raise ValueError("source recipe or baseline source differs")
            if change["recipe_sha256"] != digest(Path(module.__file__)):
                # A reader/diagnostic correction need not rebuild identical C++.
                # Authenticate the historical recipe, then independently require
                # today's source rewrite to reproduce the exact compiled bytes.
                if not candidate.get("commit"):
                    raise ValueError("historical source recipe lacks a revision")
                recipe_path = str(Path(module.__file__).resolve().relative_to(ROOT))
                historical = subprocess.check_output(["git", "show", candidate["commit"] + ":" + recipe_path], cwd=ROOT)
                if hashlib.sha256(historical).hexdigest() != change["recipe_sha256"]:
                    raise ValueError("historical source recipe differs from its revision")
            expected = hashlib.sha256(module.rewrite(path.read_text(), change["name"]).encode()).hexdigest()
            if expected != change["after_sha256"] or candidate["source_files"][module.SOURCE]["sha256"] != expected:
                raise ValueError("candidate changes more than the declared source rule")
    else:
        _, change = recipe(name)
    for key in ("upstream_commit", "simde_commit", "compiler",
                "fixture_support", "initialization", "platform", "machine"):
        if key not in baseline or baseline[key] != candidate.get(key):
            raise ValueError(f"uncontrolled build difference: {key}")
    commands = [[arg for arg in b["command"] if not re.fullmatch(r"-j\d+", arg)]
                for b in (baseline, candidate)]
    if commands[0] != commands[1]:
        raise ValueError("uncontrolled compiler command difference")
    # Compare the actual generated sources; port/support inventories also include
    # research documentation that can change without changing compiled code.
    key = source_recipe(candidate)
    changed_files = set(module.BEFORE) | {"src/b1_interp.h", "src/neif_levers.h"} if key == "metadata_variant" else {change["source_file"]}
    if key != "metadata_variant" and baseline["source_files"][change["source_file"]]["sha256"] != change["before_sha256"]:
        raise ValueError("baseline parameter source differs from upstream")
    files = [{k: v for k, v in b["source_files"].items() if k not in changed_files} for b in (baseline, candidate)]
    if files[0] != files[1]:
        raise ValueError("model source differs beyond declared parameter file")
    return name


def validate_runner(meta, protocol):
    # Build-only CLI additions need not invalidate a saved baseline encoding.
    # Verify the exact recorded runner and its unchanged benchmark function.
    source = subprocess.check_output(["git", "show", meta["commit"] + ":scripts/native_cmix.py"], cwd=ROOT)
    if hashlib.sha256(source).hexdigest() != meta["runner_sha256"]:
        raise ValueError("runner differs from its recorded source revision")
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "bench")
    sha = hashlib.sha256(ast.dump(function).encode()).hexdigest()
    if sha != protocol["runner_control"]["bench_function_ast_sha256"]:
        raise ValueError("benchmark procedure differs from the frozen protocol")


def summarize(args):
    manifest = json.loads(args.manifest.read_text())
    protocol = json.loads(args.protocol.read_text())
    inputs = protocol["fixtures"][args.role]
    if digest(args.manifest) != inputs["manifest_sha256"]:
        raise ValueError("manifest differs from the frozen experiment")
    sample = next(s for s in manifest["samples"] if s["variant"] == protocol["input_variant"])
    if sample["sha256"] != inputs["input_sha256"]:
        raise ValueError("input differs from the frozen experiment")
    helper = args.build.resolve() / "prepare-sample"
    if digest(helper) != manifest["helper_sha256"]:
        raise ValueError("inverse helper differs from the fixture")
    metadata = [json.loads((run / "metadata.json").read_text()) for run in args.runs]
    names = [model_name(meta["build"]) for meta in metadata]
    if len(names) != len(set(names)) or set(names) != set(protocol["variants"]):
        raise ValueError("requires exactly one run per declared model, including baseline")
    for name, frozen in protocol.get("variant_recipes", {}).items():
        if name not in names:
            raise ValueError("frozen recipe is absent from the trial set")
        current = recipe(name)[1]
        if any(current.get(key) != value for key, value in frozen.items()):
            raise ValueError("model recipe differs from the frozen experiment")
    if protocol.get("retrieval_recipe_sha256"):
        if protocol["retrieval_recipe_sha256"] != digest(Path(retrieval.__file__)):
            raise ValueError("retrieval recipe differs from frozen experiment")
    if protocol.get("alias_recipe_sha256"):
        if protocol["alias_recipe_sha256"] != digest(Path(alias.__file__)):
            raise ValueError("alias recipe differs from frozen experiment")
    if protocol.get("activity_recipe_sha256"):
        if protocol["activity_recipe_sha256"] != digest(Path(activity.__file__)):
            raise ValueError("activity recipe differs from frozen experiment")
    if protocol.get("bit_trace_recipe_sha256"):
        if protocol["bit_trace_recipe_sha256"] != digest(Path(bit_trace.__file__)):
            raise ValueError("bit trace recipe differs from frozen experiment")
    if protocol.get("bit_weight_recipe_sha256"):
        if protocol["bit_weight_recipe_sha256"] != digest(Path(bit_weight.__file__)):
            raise ValueError("bit-weight recipe differs from frozen experiment")
    if protocol.get("metadata_recipe_sha256"):
        if protocol["metadata_recipe_sha256"] != digest(Path(metadata_support.__file__)):
            raise ValueError("metadata recipe differs from frozen experiment")
    base = metadata[names.index("baseline")]
    records, logs = {}, []
    with tempfile.TemporaryDirectory(prefix="hutter-model-verify-") as tmp:
        for name, meta, run in zip(names, metadata, args.runs):
            compatible_builds(base["build"], meta["build"], args.build.resolve() / "source")
            validate_runner(meta, protocol)
            for key in ("platform", "machine", "cpu", "side_data", "native_arguments"):
                if key not in base or base[key] != meta.get(key):
                    raise ValueError(f"uncontrolled trial difference: {key}")
            if meta["native_arguments"] != corpus_arguments(manifest, meta["build"]):
                raise ValueError("fixture phase arguments differ")
            if digest(run / "cmix") != meta["binary_sha256"] or meta["binary_sha256"] != meta["build"]["binary_sha256"]:
                raise ValueError("trial binary differs from recorded build")
            rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
            if len(rows) != 1:
                raise ValueError("expected one complete trial per model")
            row = rows[0]
            if (row["input_sha256"], row["input_bytes"]) != (sample["sha256"], sample["bytes"]):
                raise ValueError("trial used a different input")
            if not row["roundtrip"] or not row.get("context_valid") or not row.get("repeat_matches", True):
                raise ValueError("trial failed; preserve diagnostic evidence separately")
            if any(row[phase]["status"] != "ok" for phase in ("compress", "decompress")):
                raise ValueError("trial phase did not succeed")
            archive = Path(row["compress"]["command"][-1])
            restored = Path(row["decompress"]["command"][-1])
            if digest(archive) != row["archive_sha256"] or archive.stat().st_size != row["archive_bytes"]:
                raise ValueError("archive differs from saved trial")
            if digest(restored) != sample["sha256"]:
                raise ValueError("decoded bytes differ from fixed input")
            for asset, info in meta["side_data"].items():
                path = restored.parent / ("dictionary.dic" if asset == "dictionary/english.dic" else asset)
                if digest(path) != info["sha256"] or path.stat().st_size != info["bytes"]:
                    raise ValueError("trial asset differs from record")
            context = {phase: context_report(Path(row[phase]["log"])) for phase in ("compress", "decompress")}
            validate_context(context["compress"], context["decompress"], manifest)
            if name == "z3-off" and context["compress"]["z3"]["fed_tokens"] != 0:
                raise ValueError("disabled link-prefix control still feeds tokens")
            if manifest["redirect_prefix_count"] < manifest["page_count"]:
                if any("entering main text block" not in Path(row[p]["log"]).read_text(errors="replace")
                       for p in ("compress", "decompress")):
                    raise ValueError("main text phase not observed")
            raw = Path(tmp) / (name + ".xml")
            subprocess.run([str(helper), *manifest["helper_arguments"], "decode", str(restored), str(raw)], check=True)
            final_sha = checked_restoration(raw.read_bytes(), sample, manifest)
            log_hashes = {}
            for phase in ("compress", "decompress"):
                log = Path(row[phase]["log"])
                log_hashes[phase] = digest(log)
                logs.append((log, name + "-" + phase + ".log"))
            records[name] = {"payload_bytes": row["archive_bytes"], "archive_sha256": row["archive_sha256"],
                             "binary_sha256": meta["binary_sha256"], "binary_bytes": meta["binary_bytes"],
                             "model": (meta["build"].get("retrieval_variant") or meta["build"].get("alias_variant")
                                       or meta["build"].get("activity_variant") or meta["build"].get("bit_trace_variant") or meta["build"].get("bit_weight_variant")
                                       or meta["build"].get("metadata_variant")
                                       or model_identity(meta["build"])[1]), "context": context,
                             "original_bytes_roundtrip": True, "restored_raw_sha256": final_sha,
                             "compress_seconds": row["compress"]["wall_seconds"],
                             "decompress_seconds": row["decompress"]["wall_seconds"],
                             "source_run": str(run.resolve()), "metadata_sha256": digest(run / "metadata.json"),
                             "results_sha256": digest(run / "results.jsonl"), "log_sha256": log_hashes}
    for row in records.values():
        row["delta_bytes_vs_baseline"] = row["payload_bytes"] - records["baseline"]["payload_bytes"]
    if "alias-refresh" in records and records["alias-refresh"]["context"] != records["baseline"]["context"]:
        raise ValueError("alias prediction refresh changed context feed counts")
    if "activity-mlp" in records:
        probe = records["activity-mlp"]
        if (probe["archive_sha256"] != records["baseline"]["archive_sha256"]
                or probe["context"] != records["baseline"]["context"]):
            raise ValueError("activation telemetry changed archive or context")
        run = args.runs[names.index("activity-mlp")]
        phases = {p: activity.parse_log(run / "trial-0-0" / (p + ".log"))
                  for p in ("compress", "decompress")}
        if phases["compress"] != phases["decompress"]:
            raise ValueError("encoder and decoder activation counts differ")
        probe["activity"] = phases["compress"]
        probe["activity_encoder_decoder_match"] = True
        probe["unchanged_archive"] = True
    for name, probe in records.items():
        if name.startswith("bit-weight-") and probe["context"] != records["baseline"]["context"]:
            raise ValueError("bit-weight change altered upstream context counts")
    if "bit-trace-fixture" in records:
        probe = records["bit-trace-fixture"]
        if (probe["archive_sha256"] != records["baseline"]["archive_sha256"]
                or probe["context"] != records["baseline"]["context"]):
            raise ValueError("bit trace recording changed archive or context")
        run = args.runs[names.index("bit-trace-fixture")]
        directory = run / "trial-0-0"
        phases = {p: bit_trace.inspect_log(directory / (p + ".log"), directory)
                  for p in ("compress", "decompress")}
        if phases["compress"] != phases["decompress"]:
            raise ValueError("encoder and decoder bit traces differ")
        probe["bit_trace"] = phases["compress"]
        probe["trace_encoder_decoder_match"] = True
        probe["unchanged_archive"] = True
    report = {"version": 1, "kind": "fixed-input-model-ablation", "role": args.role,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "protocol_sha256": digest(args.protocol), "manifest_sha256": digest(args.manifest),
              "input_sha256": sample["sha256"], "input_bytes": sample["bytes"],
              "raw_sha256": manifest["raw_sha256"], "raw_bytes": manifest["raw_bytes"],
              "side_data": base["side_data"], "native_arguments": base["native_arguments"],
              "verifier_sha256": digest(Path(__file__)),
              "scope": protocol.get("platform_scope", "Native fixture payloads; fixed weights; concurrent exploratory times; not prize scores"),
              "variants": records}
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.manifest, args.output / "manifest.json")
    shutil.copyfile(args.protocol, args.output / "protocol.json")
    for name, run in zip(names, args.runs):
        target = args.output / name
        target.mkdir()
        for file in ("metadata.json", "results.jsonl"):
            shutil.copyfile(run / file, target / file)
    for log, name in logs:
        shutil.copyfile(log, args.output / name)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for name, row in records.items():
        print(f'{name:16} {row["payload_bytes"]:8} {row["delta_bytes_vs_baseline"]:+6} bytes; exact original restored')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("manifest", "protocol", "build", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    parser.add_argument("--role", choices=("screen", "holdout", "confirmation"), required=True)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    try:
        summarize(args)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
