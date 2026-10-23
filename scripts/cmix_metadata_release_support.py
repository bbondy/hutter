"""Apply the isolated Ex-Girlfriend E1 forecast to an untouched release copy."""
from pathlib import Path
import shutil
import subprocess

from competitive import ENGINE
from make_samples import digest
from cmix_metadata_support import PORT, UPSTREAM_COMMIT

VARIANT = "page-id-revid-e1"
CHANGED = ("src/id_exclude.h", "src/metablock.h", "src/metablock_form.h")
ADDED = ("src/b1_interp.h", "src/neif_levers.h")


def apply(source, variant):
    if variant != VARIANT:
        raise ValueError("unknown release metadata variant")
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("release metadata patch must not modify pinned upstream")
    before = {name: digest(source / name) for name in CHANGED}
    if any(before[name] != digest(ENGINE / name) for name in CHANGED):
        raise ValueError("release metadata source differs from pinned upstream")
    if any((source / name).exists() for name in ADDED):
        raise ValueError("release metadata header already exists")
    patch = PORT / "e1.patch"
    with patch.open("rb") as file:
        subprocess.run(["patch", "-p1", "--batch", "--fuzz=0"], cwd=source,
                       stdin=file, check=True)
    for name in ADDED:
        shutil.copyfile(PORT / Path(name).name, source / name)
    return {"name": variant, "origin": "Ex-Girlfriend 1.0",
            "origin_commit": UPSTREAM_COMMIT, "license": "GPL-3.0-only",
            "patch_sha256": digest(patch), "before_sha256": before,
            "after_sha256": {name: digest(source / name) for name in CHANGED},
            "new_headers_sha256": {name: digest(source / name) for name in ADDED},
            "recipe_sha256": digest(Path(__file__)),
            "scope": "E1 page-ID/revision-ID forecast only; NEIF_E3B=0. Pinned release weights, other predictors, timestamp forecast and packer stay unchanged."}
