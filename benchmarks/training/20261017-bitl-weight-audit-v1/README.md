# Unchanged BITLSTM checkpoint and export

The published pass-32 float32 checkpoint is present: 14,748 bytes, SHA-256
`5447ed151f0503d7019ee23467d954842d128cf7e1cd4a3464c883155a022eb6`.
The unmodified upstream converter produces exactly the shipped 7,386-byte
bfloat16 file, SHA-256
`c72957f48c2ec81afa3aed2baae7acd964c17f96bb0406b8195818fc708a8e7d`.
Every byte equals the compiled `kBlob` array. Geometry, finite parameters and
zero input-padding columns pass; there are 3,681 stored values and 3,585 active
parameters.

This reproduces an export, not training. The original trace, channel file and
the development tree containing their writer are absent. The upstream 20% cut
records 25,130,230,588 trace bytes and 14,449,882,600 channel bytes. A replacement
writer needs archive identity and per-bit replay validation before new training.
The derived blob stays local because the same bytes are already embedded in
pinned source. No model or compression result changed.
