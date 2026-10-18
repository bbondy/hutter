#!/usr/bin/env python3
"""Measure deterministic MLP-neuron permutations with the upstream weight coder.

Requires NumPy. This is a container experiment, not an inference-equivalence
claim: candidate tensors must also pass the actual kernels and coder traces.
"""
import argparse
import datetime
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ENGINE / "training/tf/4_export"
# Import the pinned reader without generating files inside the upstream tree.
sys.dont_write_bytecode = True
sys.path.insert(0, str(EXPORT))
import prune_dead_neurons as upstream

wc = upstream.wc3
VARIANTS = ("mlp-scale", "mlp-zero-count", "mlp-row-mean")


def permute(entries, variant):
    if variant not in VARIANTS:
        raise ValueError("unknown permutation")
    arrays = {name: array for name, _, array in entries}
    changed, permutations = {}, {}
    for layer in range(16):
        prefix = f"blocks.{layer}.mlp."
        up_name, scale_name, down_name = (prefix + suffix for suffix in
                                         ("up.weight.q", "up.weight.scale", "down.weight.q"))
        up, scale, down = (arrays[name] for name in (up_name, scale_name, down_name))
        n = up.shape[0]
        if (up.dtype != np.int8 or up.shape != (n, 192) or not 0 < n <= 768
                or scale.dtype != np.uint16 or scale.shape != (n,)
                or down.dtype != np.int8 or down.shape != (192, n)):
            raise ValueError(f"unexpected MLP geometry at layer {layer}")
        if np.any(np.abs(up.astype(np.int16)) > 7) or np.any(np.abs(down.astype(np.int16)) > 7):
            raise ValueError("weight exceeds the int4 kernel bound")
        allowed = {up_name, scale_name, prefix + "up.quantize_activation.scale"}
        if any(name.startswith(prefix + "up.") and name not in allowed for name in arrays):
            raise ValueError("additional up-projection tensor needs an explicit permutation rule")
        scales = wc._bf16_to_f32(scale)
        if not np.isfinite(scales).all():
            raise ValueError("nonfinite scale invalidates the equivalence argument")
        key = {"mlp-scale": lambda: np.abs(scales),
               "mlp-zero-count": lambda: (up == 0).sum(axis=1),
               "mlp-row-mean": lambda: up.astype(np.int64).sum(axis=1)}[variant]()
        order = np.argsort(key, kind="stable")
        inverse = np.argsort(order)
        new_up, new_scale, new_down = up[order, :], scale[order], down[:, order]
        if (new_up[inverse, :].tobytes() != up.tobytes()
                or new_scale[inverse].tobytes() != scale.tobytes()
                or new_down[:, inverse].tobytes() != down.tobytes()):
            raise ValueError("inverse permutation failed")
        changed.update({up_name: new_up, scale_name: new_scale, down_name: new_down})
        permutations[str(layer)] = order.tolist()
    result = [(name, code, changed.get(name, array)) for name, code, array in entries]
    return result, permutations


def check_tensors(want, got):
    if [name for name, _, _ in want] != list(got):
        raise ValueError("tensor order differs after reading the container")
    for name, code, array in want:
        actual_code, actual = got[name]
        if (actual_code != code or actual.dtype != array.dtype or actual.shape != array.shape
                or actual.tobytes() != array.tobytes()):
            raise ValueError("container changed tensor " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    if protocol["variants"] != list(VARIANTS):
        raise ValueError("protocol differs from the fixed permutation recipes")
    manifest = json.loads(MANIFEST.read_text())
    if any(differences(manifest["files"], inventory(ENGINE)).values()):
        raise ValueError("pinned upstream source differs")
    original = ENGINE / protocol["weights_file"]
    if digest(original) != protocol["weights_sha256"]:
        raise ValueError("weight container differs from protocol")
    output = args.output.resolve()
    if output.is_relative_to(ENGINE):
        raise ValueError("outputs must be outside the pinned source")
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "mlp-weight-permutation-screen", "version": 1,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "script_sha256": digest(Path(__file__)), "protocol_sha256": digest(args.protocol),
              "upstream_commit": manifest["commit"], "python": sys.version, "numpy": np.__version__,
              "platform": platform.platform(), "weights_sha256": digest(original),
              "original_container_bytes": original.stat().st_size,
              "upstream_writer_sha256": digest(EXPORT / "weights_compress_v3.py"),
              "scope": "Exact candidate tensor reconstruction and inverse permutations; inference and packaged submission not yet verified.",
              "variants": {}}

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    _, entries = upstream.read_container(str(original))
    report["tensor_count"] = len(entries)
    identity = output / "identity.c4"
    wc.write_tensor_file_v4(str(identity), entries)
    report["upstream_writer_identity"] = digest(identity) == digest(original)
    save()
    if not report["upstream_writer_identity"]:
        raise ValueError("writer does not reproduce the pinned container exactly")
    print("Upstream container rewrite is byte-identical", flush=True)
    for variant in VARIANTS:
        started = time.monotonic()
        candidate, permutations = permute(entries, variant)
        container = output / (variant + ".c4")
        wc.write_tensor_file_v4(str(container), candidate)
        check_tensors(candidate, wc.read_tensor_file_v3(str(container)))
        mapping = output / (variant + "-permutations.json")
        mapping.write_text(json.dumps(permutations, separators=(",", ":")) + "\n")
        delta = container.stat().st_size - original.stat().st_size
        report["variants"][variant] = {
            "container_bytes": container.stat().st_size, "container_sha256": digest(container),
            "delta_container_bytes": delta, "gross_two_container_delta_bytes": 2 * delta,
            "permutations_sha256": digest(mapping), "tensor_roundtrip": True,
            "inverse_permutations_exact": True,
            "displaced_neurons": sum(sum(i != j for i, j in enumerate(order)) for order in permutations.values()),
            "wall_seconds": time.monotonic() - started,
            "note": "Two-copy accounting excludes binding/packed-binary size changes; model inference remains unverified."}
        save()
        print(variant, container.stat().st_size, f"{delta:+d} bytes per container", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
