# Isolated E1 metadata release-component cost

[Native Linux workflow run 40009128933](https://github.com/bbondy/hutter/actions/runs/40009128933)
reproduced the exact published untouched `comp9` SHA-256 with Clang 18 and
the pinned GCC 13 headers. It then built the E1-only metadata derivative on
the same host. Both original packer self-check suites passed. The downloaded
packages and decoder prefixes were independently re-inspected; the local
comparison is byte-identical to the CI comparison.

| Component | Untouched | E1 only | Change |
| --- | ---: | ---: | ---: |
| Packed `comp9` | 4,000,689 B | 4,001,789 B | **+1,100 B** |
| Independent decoder prefix | 165,545 B | 166,539 B | **+994 B** |
| Measured release components excluding payload/dictionary/footer | 7,882,901 B | 7,884,995 B | **+2,094 B** |

The external transformer-weight, hint and order blocks are byte-identical.
The two small Mac fixtures saved 13 and 16 payload bytes; those observations
do not yet pay for the measured package increase. A full-stream E1 payload
delta is needed before considering it a net prize improvement. This component
comparison is not a full enwik9 archive, independent self-extracting decode
or resource-eligibility result. The [comparison](comparison.json), both
build reports/logs and [download verification](verification.json) are kept.
