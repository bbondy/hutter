# Full training-row dump reproduced on native Mac

The complete 7,117,383,324-byte row dump matches the published SHA-256:
`58fc6c74c09400192c28cf3608e6eeb0387ba4f40b4255d39dbc8ac5e0bf66a0`.
All three zone/match rasters have exactly 552,750,204 bytes. Their hashes are
recorded in `report.json`; the runtime reports the same coded-stream count.
The build uses the frozen canonical full preprocessing, original retrieval
rule and upstream TRAIN_MODE=2 diagnostic. It does not run transformer inference.

The completed diagnostic took about 2,406 seconds with 4,636,557,312 bytes peak
RSS in this concurrent local run. These numbers describe this diagnostic only,
not compression speed or prize eligibility. Near 97%, two point profiles showed
heavy history-file seek/read work; the separate read-cache experiment must
reproduce this same dump and raster hashes before its results are accepted.

Report, protocol, compile log and complete dump log are retained. The source
revision/script, binary, protocol and log hashes were checked again before
saving. The multi-gigabyte datasets stay local. This establishes data
reproduction, not a trained model, decodable archive or improved prize score.
