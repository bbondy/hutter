INPUT ?= data/sample.txt
ARCHIVE ?= build/$(notdir $(INPUT)).ahf
RESTORED ?= build/$(notdir $(INPUT)).restored
CODEC ?= huffman
ENWIK8_URL ?= http://mattmahoney.net/dc/enwik8.zip
ENWIK8_ZIP ?= data/enwik8.zip
ENWIK8 ?= data/enwik8
ENWIK8_SHA1 ?= 57b8363b814821dc9d47aa4d41f58733519076b2
ENWIK9_URL ?= http://mattmahoney.net/dc/enwik9.zip
ENWIK9_ZIP ?= data/enwik9.zip
ENWIK9 ?= data/enwik9
ENWIK9_SHA1 ?= 2996e86fb978f93cca8f566cc56998923e7fe581

.PHONY: build test fmt clean roundtrip bench help corpora data-files enwik8 enwik9 verify-enwik8 verify-enwik9

help:
	@echo "make build                    Compile the Rust CLI"
	@echo "make test                     Run unit tests"
	@echo "make fmt                      Format the code"
	@echo "make corpora                  Download and verify enwik8 and enwik9"
	@echo "make data-files               Alias for corpora"
	@echo "make enwik8                   Download and verify enwik8 if needed"
	@echo "make enwik9                   Download and verify enwik9 if needed"
	@echo "make verify-enwik8            Verify the local enwik8 checksum"
	@echo "make verify-enwik9            Verify the local enwik9 checksum"
	@echo "make roundtrip INPUT=path CODEC=huffman|huffman-o1|lz77|ppm-o1|ppm-o2|ppm|ppm-o4|ppm-o5|ppm-o6|ppm-bit-o1|ppm-bit-o2|ppm-bit|ppm-bit-o4|ppm-bit-o5|ppm-bit-o6|ppm-bit-mix   Compress + decompress + verify"
	@echo "                              Note: ppm-oN is byte-level PPM; ppm-bit-oN is bit-level PPM"
	@echo "make bench INPUT=path CODEC=huffman|huffman-o1|lz77|ppm-o1|ppm-o2|ppm|ppm-o4|ppm-o5|ppm-o6|ppm-bit-o1|ppm-bit-o2|ppm-bit|ppm-bit-o4|ppm-bit-o5|ppm-bit-o6|ppm-bit-mix       Print size stats for a corpus"
	@echo "                              Note: ppm-oN is byte-level PPM; ppm-bit-oN is bit-level PPM"
	@echo "make clean                    Remove build artifacts"

build:
	cargo build --release

test:
	cargo test

fmt:
	cargo fmt

roundtrip: build
	mkdir -p build
	target/release/hutter-starter compress --codec $(CODEC) $(INPUT) $(ARCHIVE)
	target/release/hutter-starter decompress $(ARCHIVE) $(RESTORED)
	cmp $(INPUT) $(RESTORED)
	@echo "roundtrip ok: $(INPUT) -> $(ARCHIVE) -> $(RESTORED)"

bench: build
	mkdir -p build
	target/release/hutter-starter compress --codec $(CODEC) $(INPUT) $(ARCHIVE)
	target/release/hutter-starter stats $(INPUT) $(ARCHIVE)

corpora: enwik8 enwik9

data-files: corpora

enwik8: $(ENWIK8)

$(ENWIK8):
	mkdir -p data
	if [ -f "$(ENWIK8)" ]; then \
		echo "enwik8 already exists at $(ENWIK8)"; \
	else \
		echo "downloading $(ENWIK8_URL)"; \
		curl -fL "$(ENWIK8_URL)" -o "$(ENWIK8_ZIP)"; \
		unzip -o "$(ENWIK8_ZIP)" -d data; \
	fi
	$(MAKE) verify-enwik8

enwik9: $(ENWIK9)

$(ENWIK9):
	mkdir -p data
	if [ -f "$(ENWIK9)" ]; then \
		echo "enwik9 already exists at $(ENWIK9)"; \
	else \
		echo "downloading $(ENWIK9_URL)"; \
		curl -fL "$(ENWIK9_URL)" -o "$(ENWIK9_ZIP)"; \
		unzip -o "$(ENWIK9_ZIP)" -d data; \
	fi
	$(MAKE) verify-enwik9

verify-enwik8:
	test -f "$(ENWIK8)"
	echo "$(ENWIK8_SHA1)  $(ENWIK8)" | shasum -a 1 -c -

verify-enwik9:
	test -f "$(ENWIK9)"
	echo "$(ENWIK9_SHA1)  $(ENWIK9)" | shasum -a 1 -c -

clean:
	rm -rf build target
