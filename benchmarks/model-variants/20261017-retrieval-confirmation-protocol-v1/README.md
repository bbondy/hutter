# Reserved-range confirmation

The unchanged exact-target filter saved 5 and 2 fixture payload bytes on the
two reused Mac inputs. This activates the previously declared third range,
requested at byte 80,000,000 with a 1,000,000-byte target in official enwik8.
The complete-page selector produces `[80020050, 81020844)`: 1,000,794 raw bytes,
150 pages, with 52 pages in the projected upstream front block. The canonical
upstream-order prepared stream is 924,454 bytes. Hashes are in `confirmation.json`.

The fixture is prepared with the same canonical entity conversion, exact
upstream order index and phase protocol as the first two sets. All preparation
variants restore the original bytes; only the upstream-order stream is used
for this model comparison. No coder results were observed when this protocol
was frozen. No model parameter, weight, retrieval recipe or sample-selection
rule changes after the screening results.

Run the original baseline and existing exact-target build on this stream, then
use `model_history.py --role confirmation` with `protocol.json`. Native Linux
replays and verifies the same manifest:

```sh
gh workflow run linux-benchmarks.yml --ref main -f experiment=exact-target-confirmation
```

Keep losses as well as gains. This range becomes examined evidence after this
test; it must not be advertised as untouched validation for later tuning.
The upstream model was already trained on enwik9, which contains this range.
