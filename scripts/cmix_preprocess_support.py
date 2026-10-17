"""Define the inherited XML entity arithmetic without signed-overflow assumptions."""
from pathlib import Path

from competitive import ENGINE
from make_samples import digest

HEADER = "src/readalike_prepr/phda9_preprocess.h"
CAPABILITY = "phda9-entities-u32-v1"
OLD = "k = k*256 + ' ';"
NEW = "k = (int)(((unsigned int)k << 8) + (unsigned int)' ');"


def apply_portable_preprocessing(source):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("preprocessing fixes must not modify pinned upstream")
    path = source / HEADER
    text = path.read_text()
    if text.count(OLD) != 2:
        raise ValueError("expected exactly two inherited entity arithmetic sites")
    before = digest(path)
    path.write_text(text.replace(OLD, NEW))
    return {"capability": CAPABILITY, "source_file": HEADER, "before_sha256": before,
            "after_sha256": digest(path), "patcher_sha256": digest(Path(__file__))}
