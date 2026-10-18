"""Embed one frozen trained BITLSTM checkpoint in a disposable source copy."""
import hashlib
from pathlib import Path
import re

from competitive import ENGINE
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "src/bit_head_weights.h"
VARIANT = "warm-start-lr3000-v1"
MODEL = ROOT / "benchmarks/training/20261017-bitl-warm-start-v1/models/lr3000.nblb"
MODEL_SHA = "bfd6401b0142441e7b99a4fe930943d830e7dca2e47d08692e83b023a642f8e0"
ORIGINAL_SHA = "c72957f48c2ec81afa3aed2baae7acd964c17f96bb0406b8195818fc708a8e7d"


def rewrite(text, variant=VARIANT):
    if variant != VARIANT:
        raise ValueError("unknown trained bit-model variant")
    if text != (ENGINE / SOURCE).read_text():
        raise ValueError("trained bit-model source anchor changed")
    data = MODEL.read_bytes()
    if len(data) != 7386 or hashlib.sha256(data).hexdigest() != MODEL_SHA:
        raise ValueError("frozen trained bit-model bytes changed")
    match = re.search(r'(static const unsigned char kBlob\[7386\] = \{)(.*?)(\n\};)', text, re.S)
    if not match or text.count(ORIGINAL_SHA) != 1:
        raise ValueError("trained bit-model array anchor changed")
    body = "\n" + "\n".join("  " + ",".join(f"0x{x:02x}" for x in data[i:i+16]) + ","
                              for i in range(0, len(data), 16))
    return (text[:match.start(2)] + body + text[match.end(2):]).replace(ORIGINAL_SHA, MODEL_SHA)


def apply(source, variant):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("bit-model embedding must not modify pinned upstream")
    path = source / SOURCE
    before = digest(path)
    changed = rewrite(path.read_text(), variant)
    path.write_text(changed)
    return {"name": variant, "source_file": SOURCE, "before_sha256": before,
            "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            "recipe_sha256": digest(Path(__file__)), "model_sha256": MODEL_SHA,
            "model_bytes": 7386, "model_path": str(MODEL.relative_to(ROOT)),
            "scope": "Only the embedded BF16 array and its hash comment change. Model code, geometry, online-learning threshold, transformer weights and all other sources remain unchanged."}
