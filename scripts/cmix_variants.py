"""Small, named model experiments applied only to disposable source copies."""
import hashlib
from pathlib import Path

from competitive import ENGINE
from make_samples import digest

HEADER = "src/tf1/tf1_z3.h"
DEPTH_HEADER = "src/adaptive_depth.h"
DEFAULTS = {"budget": 256, "chunk": 64, "max_mentions": 8, "line_scan": 512, "open_len": 1}
DEPTH_VARIANTS = {"depth-tau9": 9000, "depth-no-skip": 31000}
VARIANTS = {
    "baseline": {},
    "z3-budget128": {"budget": 128},
    "z3-chunk32": {"chunk": 32},
    "z3-off": {"budget": 0},
    **{name: {} for name in DEPTH_VARIANTS},
}


def recipe(name):
    if name not in VARIANTS:
        raise ValueError(f"unknown model variant: {name}")
    source_file = DEPTH_HEADER if name in DEPTH_VARIANTS else HEADER
    original = (ENGINE / source_file).read_text()
    changed = original
    parameters = {"z3_parameters": {**DEFAULTS, **VARIANTS[name]}}
    if name in DEPTH_VARIANTS:
        anchor = "static const float kTau = (float)(8000) * 0.001f;"
        if changed.count(anchor) != 1:
            raise ValueError("adaptive-depth threshold anchor changed")
        changed = changed.replace(anchor, anchor.replace("8000", str(DEPTH_VARIANTS[name])))
        parameters["adaptive_depth_parameters"] = {"tau_per_mille": DEPTH_VARIANTS[name]}
    for key, value in VARIANTS[name].items():
        anchor = f"  int {key} = {DEFAULTS[key]};"
        if changed.count(anchor) != 1:
            raise ValueError(f"model parameter anchor changed: {key}")
        changed = changed.replace(anchor, f"  int {key} = {value};")
    sha = lambda text: hashlib.sha256(text.encode()).hexdigest()
    return changed, {
        "name": name, **parameters,
        "source_file": source_file, "before_sha256": sha(original), "after_sha256": sha(changed),
        "recipe_sha256": digest(Path(__file__)),
    }


def apply_variant(source, name):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("model variants must not modify the pinned upstream")
    changed, info = recipe(name)
    path = source / info["source_file"]
    if digest(path) != info["before_sha256"]:
        raise ValueError("model variant requires the unchanged upstream parameter header")
    if name != "baseline":
        path.write_text(changed)
    return info


def model_identity(build):
    """Accept historical baseline builds only with their saved default header hash."""
    saved = build.get("model_variant")
    _, expected = recipe(saved["name"] if saved else "baseline")
    if saved and any(saved.get(key) != expected.get(key) for key in
                     ("name", "z3_parameters", "adaptive_depth_parameters", "source_file", "before_sha256", "after_sha256")):
        raise ValueError("model variant differs from the declared recipe")
    if build["source_files"][expected["source_file"]]["sha256"] != expected["after_sha256"]:
        raise ValueError("model source hash differs from its declared variant")
    if expected["source_file"] == DEPTH_HEADER:
        if build["source_files"][HEADER]["sha256"] != recipe("baseline")[1]["after_sha256"]:
            raise ValueError("adaptive-depth trial changes link-context source too")
        return expected["name"], {"z3": expected["z3_parameters"],
                                  "adaptive_depth": expected["adaptive_depth_parameters"]}
    if build["source_files"][DEPTH_HEADER]["sha256"] != digest(ENGINE / DEPTH_HEADER):
        raise ValueError("undeclared adaptive-depth source change")
    return expected["name"], expected["z3_parameters"]


def require_same_model(left, right):
    if model_identity(left) != model_identity(right):
        raise ValueError("model variants differ; cannot interpret this as platform parity")
