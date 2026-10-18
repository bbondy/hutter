# The replay mismatch is explained by the math provider

The original standalone public trainer first mismatched at bit 665,047 on the
screen and 281,491 on the disjoint fixture. Recompiling the baseline runtime
head with its own recorded flags but linking system math produces those same
first mismatches. The first diagnostic attempt looked for an object that the
compressor build had removed; its failed build log is retained. The successful
control recompiles the verified source into a new diagnostic directory.

The compressor defines exp/log and float variants in src/detmath.cpp. The
public trainer build script does not link that file. Adding exactly this math
source, under the live makefile's DETNUM_CXXFLAGS, gives complete agreement for
all 2,418,045 screen and 2,399,939 disjoint probabilities, both with the runtime
head and with the public trainer model. Model inputs and weights are unchanged.

Commands, binary/object/source hashes and logs are retained. Small diagnostic
scripts record the local control procedure; raw traces remain local. This
explains these observed Mac mismatches, not every possible platform issue.
The v3 frozen replay protocol repeats full positive and deliberately wrong
probability checks using the runtime math provider before training. Old failures
and protocols remain immutable.
