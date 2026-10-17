# Agent instructions

- Sign every commit made for this repository. Before committing, check that Git has a working signing key and `commit.gpgsign=true`; use `git commit -S` when in doubt.
- Before pushing a new commit, verify its signature with `git log -1 --show-signature`. A missing or bad signature is a failed commit, even if tests pass. Fix the signing setup before making another commit.
- Keep benchmark claims tied to saved input, binary, asset and result hashes. Distinguish fixture payload sizes from a full Hutter Prize submission score.
