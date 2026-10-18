"""A frozen exact-target retrieval experiment on disposable model sources."""
import hashlib
from pathlib import Path

from competitive import ENGINE
from make_samples import digest

SOURCE = "src/tf1/tf1_z3.cpp"
VARIANT = "exact-target"


def rewrite(text, variant=VARIANT):
    if variant != VARIANT:
        raise ValueError("unknown retrieval variant")
    changes = [
        ("  unsigned char probe[kMaxTitleTokens];", "  unsigned char probe[kMaxTitleTokens + 1];"),
        ("      if (s + title_len > pos_) continue;\n"
         "      ReadRange(s, s + title_len, probe);\n"
         "      if (memcmp(probe, title_.data(), (size_t)title_len) == 0) {",
         "      // The title and its target delimiter must already be decoded.\n"
         "      if (s + title_len >= article_start_) continue;\n"
         "      ReadRange(s, s + title_len + 1, probe);\n"
         "      // WRT represents the link pipe by byte 0x51; these are token indices.\n"
         "      const unsigned char end = probe[title_len];\n"
         "      const bool target_end = end == transformer::kByteToIndex[0x5d]\n"
         "          || end == transformer::kByteToIndex[0x51]\n"
         "          || end == transformer::kByteToIndex[0x23];\n"
         "      if (target_end && memcmp(probe, title_.data(), (size_t)title_len) == 0) {")]
    for before, after in changes:
        if text.count(before) != 1:
            raise ValueError("retrieval patch anchor changed")
        text = text.replace(before, after)
    return text


def apply(source, variant):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("retrieval experiments must not modify pinned upstream")
    path = source / SOURCE
    before = digest(path)
    changed = rewrite(path.read_text(), variant)
    path.write_text(changed)
    return {"name": variant, "source_file": SOURCE, "before_sha256": before,
            "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            "recipe_sha256": digest(Path(__file__)),
            "scope": "Require an already-decoded ], WRT pipe, or section marker after the exact title; case and underscore handling unchanged."}
