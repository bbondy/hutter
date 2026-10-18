# Coverage-analyzer assumption corrected

The first summary rejected a byte-identical, published-valid dump because it
incorrectly limited every input token to 0–207. Upstream has eight digit-run
sentinel input tokens 208–215, all on inserted rows. The 208-symbol prediction
output is a different vocabulary. The previous-token reset marker is 216.

The saved diagnosis checks ordering, final source position and reserved fields,
and identifies every higher token and its flags. All higher tokens are valid
inserted sentinels. The dump itself passed its full published SHA-256 and was
not changed. The corrected analyzer validates these input roles explicitly;
a regression test accepts 208/215 only as inserted rows and rejects 216 as a
current token, source-position sentinels and inconsistent inserted flags.
