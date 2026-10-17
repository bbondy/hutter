"""Small, named model experiments applied only to disposable source copies."""
import hashlib
from pathlib import Path

from competitive import ENGINE
from make_samples import digest

HEADER = "src/tf1/tf1_z3.h"
DEFAULTS = {"budget": 256, "chunk": 64, "max_mentions": 8, "line_scan": 512, "open_len": 1}
VARIANTS = {
    "baseline": {},
    "z3-budget128": {"budget": 128},
    "z3-chunk32": {"chunk": 32},
    "z3-off": {"budget": 0},
}


def recipe(name):
    if name not in VARIANTS:
        raise ValueError(f"unknown model variant: {name}")
    original = (ENGINE / HEADER).read_text()
    changed = original
    for key, value in VARIANTS[name].items():
        anchor = f"  int {key} = {DEFAULTS[key]};"
        if changed.count(anchor) != 1:
            raise ValueError(f"model parameter anchor changed: {key}")
        changed = changed.replace(anchor, f"  int {key} = {value};")
    sha = lambda text: hashlib.sha256(text.encode()).hexdigest()
    return changed, {
        "name": name, "z3_parameters": {**DEFAULTS, **VARIANTS[name]},
        "source_file": HEADER, "before_sha256": sha(original), "after_sha256": sha(changed),
        "recipe_sha256": digest(Path(__file__)),
    }


def apply_variant(source, name):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("model variants must not modify the pinned upstream")
    changed, info = recipe(name)
    path = source / HEADER
    if digest(path) != info["before_sha256"]:
        raise ValueError("model variant requires the unchanged upstream parameter header")
    if name != "baseline":
        path.write_text(changed)
    return info


def model_identity(build):
    """Accept historical baseline builds only with their saved default header hash."""
    saved = build.get("model_variant")
    _, expected = recipe(saved["name"] if saved else "baseline")
    if saved and any(saved.get(key) != expected[key] for key in
                     ("name", "z3_parameters", "source_file", "before_sha256", "after_sha256")):
        raise ValueError("model variant differs from the declared recipe")
    if build["source_files"][HEADER]["sha256"] != expected["after_sha256"]:
        raise ValueError("model source hash differs from its declared variant")
    return expected["name"], expected["z3_parameters"]


def require_same_model(left, right):
    if model_identity(left) != model_identity(right):
        raise ValueError("model variants differ; cannot interpret this as platform parity")
