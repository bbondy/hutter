"""Apply the pinned Ex-Girlfriend E1 metadata forecast in a disposable build."""
from pathlib import Path
import shutil
import subprocess

from competitive import ENGINE
from make_samples import digest

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "engines/ports/cmix-neif-metadata-e1"
VARIANT = "page-id-revid-e1"
UPSTREAM_COMMIT = "e923faec085a93d24bf519986ee2881497e97934"
BEFORE = {
    "src/metablock.h": "d1a6d4970a1993ae596edaa395e3dfb9d06754c81be31249d10d586c73737dd3",
    "src/metablock_form.h": "0aa598ffb98c5ea448197fce3ca99a40c8071df6121d93ba6d150f828571a236",
    "src/id_exclude.h": "faa8b21e19a690e4fd7638d237430c3c75f5fcc9055fdc39a8eea58fb718215a",
}


def apply(source, variant):
    if variant != VARIANT:
        raise ValueError("unknown metadata variant")
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("metadata experiment must not modify pinned upstream")
    patch = PORT / "e1-fixture.patch"
    changed = tuple(BEFORE)
    before = {name: digest(source / name) for name in changed}
    if before != BEFORE:
        raise ValueError("native fixture metadata source differs from frozen E1 patch base")
    with patch.open("rb") as stream:
        subprocess.run(["patch", "-p1", "--batch", "--fuzz=0"], cwd=source,
                       stdin=stream, check=True)
    for name in ("b1_interp.h", "neif_levers.h"):
        shutil.copyfile(PORT / name, source / "src" / name)
    return {
        "name": variant, "origin": "Ex-Girlfriend 1.0", "origin_commit": UPSTREAM_COMMIT,
        "license": "GPL-3.0-only", "patch_sha256": digest(patch),
        "original_upstream_patch_sha256": digest(PORT / "e1.patch"),
        "before_sha256": before,
        "after_sha256": {name: digest(source / name) for name in changed},
        "new_headers_sha256": {name: digest(PORT / name) for name in ("b1_interp.h", "neif_levers.h")},
        "recipe_sha256": digest(Path(__file__)),
        "scope": "Only E1 page-ID/revision-ID reversible metadata forecast. NEIF_E3B=0; original predictor, transformer, weights and timestamp forecast remain unchanged.",
    }
