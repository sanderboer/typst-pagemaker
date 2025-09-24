# A101 PageMaker build system
# Variables
ORG?=examples/sample.org
TYP?=deck.typ
PDF?=deck.pdf
HTML?=index.html
IR?=deck.json
GEN=../src/gen_typst.py
TYPST?=typst
PY?=python3

.PHONY: all build pdf typst ir watch clean assets check debug-overlay

all: build

build: $(PDF)
	@echo 'Build complete -> $(PDF)'

$(TYP): $(ORG) $(GEN)
	$(PY) $(GEN) $(ORG) -o $(TYP) --ir $(IR) --update-html $(HTML)

$(PDF): $(TYP)
	$(TYPST) compile --font-path ../assets/fonts --font-path ../assets/fonts/static $(TYP) $(PDF)

assets:
	@refs=$$(grep -E '^(\\[\\[file:|:PDF:)' $(ORG) | sed -E -e 's/^\\[\\[file:([^]]*)\\]\\].*/\1/' -e 's/^:PDF:[[:space:]]*//'); \
	missing=0; \
	for r in $$refs; do \
	  if [ ! -f "$$r" ]; then echo "Missing asset: $$r"; missing=1; fi; \
	done; \
	if [ $$missing -eq 0 ]; then echo 'All assets present'; else echo 'Asset check failed'; exit 1; fi

ir: $(ORG) $(GEN)
	$(PY) $(GEN) $(ORG) -o $(TYP) --ir $(IR) --update-html $(HTML)

watch: build
	$(PY) watch.py --org $(ORG) --pdf $(PDF) --typ $(TYP) --html $(HTML)

clean:
	rm -f $(TYP) $(PDF) $(IR)

check: assets build

debug-overlay:
	@echo "Building debug overlay test with custom fonts..."
	cd .. && $(PY) src/gen_typst.py examples/debug_overlay_test.org -o debug_overlay_test.typ
	cd .. && $(TYPST) compile --font-path assets/fonts --font-path assets/fonts/static debug_overlay_test.typ debug_overlay_test.pdf
	@echo "Debug overlay test complete -> ../debug_overlay_test.pdf"

# Test targets
.PHONY: test test-unit test-integration test-verbose

test:
	@echo "Running all tests..."
	python -m unittest discover tests -v

test-unit:
	@echo "Running unit tests..."
	python -m unittest discover tests/unit -v

test-integration: 
	@echo "Running integration tests..."
	python -m unittest discover tests/integration -v

test-verbose:
	@echo "Running tests with maximum verbosity..."
	python -m unittest discover tests -v -b

test-coverage:
	@echo "Running tests with coverage..."
	python -m coverage run -m unittest discover tests
	python -m coverage report
	python -m coverage html
