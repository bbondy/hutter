INPUT ?= data/sample.txt
ARCHIVE ?= build/$(notdir $(INPUT)).ahf
RESTORED ?= build/$(notdir $(INPUT)).restored
ENWIK9_URL ?= http://mattmahoney.net/dc/enwik9.zip
ENWIK9_ZIP ?= data/enwik9.zip
ENWIK9 ?= data/enwik9
ENWIK9_SHA1 ?= 2996e86fb978f93cca8f566cc56998923e7fe581

.PHONY: build test fmt clean roundtrip bench help enwik9 verify-enwik9

help:
	@echo "make build                    Compile the Rust CLI"
	@echo "make test                     Run unit tests"
	@echo "make fmt                      Format the code"
	@echo "make enwik9                   Download and verify enwik9 if needed"
	@echo "make verify-enwik9            Verify the local enwik9 checksum"
	@echo "make roundtrip INPUT=path     Compress + decompress + verify"
	@echo "make bench INPUT=path         Print size stats for a corpus"
	@echo "make clean                    Remove build artifacts"

build:
	cargo build --release

test:
	cargo test

fmt:
	cargo fmt

roundtrip: build
	mkdir -p build
	target/release/hutter-starter compress $(INPUT) $(ARCHIVE)
	target/release/hutter-starter decompress $(ARCHIVE) $(RESTORED)
	cmp $(INPUT) $(RESTORED)
	@echo "roundtrip ok: $(INPUT) -> $(ARCHIVE) -> $(RESTORED)"

bench: build
	mkdir -p build
	target/release/hutter-starter compress $(INPUT) $(ARCHIVE)
	target/release/hutter-starter stats $(INPUT) $(ARCHIVE)

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

verify-enwik9:
	test -f "$(ENWIK9)"
	echo "$(ENWIK9_SHA1)  $(ENWIK9)" | shasum -a 1 -c -

clean:
	rm -rf build target
