"""Bind one explicit experimental container in a disposable development build."""
from pathlib import Path
import shutil

from competitive import ENGINE
from make_samples import digest

WEIGHTS = "weights-poc8m_w2048_p15f_v3bf16_gestrichen_v4.c4"
HEADER = "src/transformer.h"
ORIGINAL_FINGERPRINT = 0xb263b35196aa775b


def fingerprint(path):
    result = 14695981039346656037
    for byte in path.read_bytes():
        result = ((result ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return result


def stamp(text, value):
    anchor = "inline unsigned long long WeightsFingerprint() {\n  return 0xb263b35196aa775bULL;\n}"
    if text.count(anchor) != 1:
        raise ValueError("original weight fingerprint anchor changed")
    return text.replace(anchor, anchor.replace("0xb263b35196aa775b", f"0x{value:016x}"))


def apply_container(source, container):
    if source.resolve().is_relative_to(ENGINE):
        raise ValueError("weight experiments must not modify pinned upstream")
    if (source / WEIGHTS).read_bytes() != (ENGINE / WEIGHTS).read_bytes():
        raise ValueError("requires the original weight container in the build copy")
    if container.read_bytes()[:8] != b"FX2TFWC4":
        raise ValueError("requires a format-v4 weight container")
    if fingerprint(ENGINE / WEIGHTS) != ORIGINAL_FINGERPRINT:
        raise ValueError("pinned container fingerprint differs")
    header = source / HEADER
    before = digest(header)
    value = fingerprint(container)
    changed = stamp(header.read_text(), value)
    shutil.copyfile(container, source / WEIGHTS)
    header.write_text(changed)
    return {"capability": "explicit-weight-container-v1", "container_sha256": digest(container),
            "container_bytes": container.stat().st_size, "fingerprint_fnv1a64": f"{value:016x}",
            "original_sha256": digest(ENGINE / WEIGHTS), "source_file": HEADER,
            "before_header_sha256": before, "after_header_sha256": digest(header),
            "patcher_sha256": digest(Path(__file__))}
