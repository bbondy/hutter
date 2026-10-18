# Isolated E1 metadata experiment

This GPL-3.0-only experimental port extracts the E1 page-ID/revision-ID
forecast from Ryan Landay's [Ex-Girlfriend 1.0](https://github.com/rlanday/ex-girlfriend/tree/v1.0),
commit `e923faec085a93d24bf519986ee2881497e97934`, a derivative of
Marcus Wölk's cmix-neif 1.0. Landay's `EX-GIRLFRIEND.md`, `NOTICE.md`,
`LICENSE`, inherited notices and third-party license texts govern the copied
source. The unmodified cmix-neif snapshot and its notices remain in this repo.

`e1.patch` is the exact change to the three upstream metadata headers.
`e1-fixture.patch` applies the same E1 logic after this repo's native
small-corpus count instrumentation. `b1_interp.h` is copied unchanged from the
pinned derivative; `neif_levers.h` changes only the default `NEIF_E3B` setting
from 1 to 0 so the timestamp experiment stays separate. The Python builder
checks the instrumented source hashes and applies the patch only to a disposable
build copy. No source here establishes a prize-eligible archive by itself.
