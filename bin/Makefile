# A101 PageMaker build system
# Variables
ORG?=examples/sample.org
TYP?=deck.typ
PDF?=deck.pdf
HTML?=index.html
IR?=deck.json
# Legacy script retired; use CLI
TYPST?=typst
PY?=python3
 
.PHONY: all build pdf typst ir watch clean assets check debug-overlay help test test-unit test-integration test-verbose test-coverage
 
all: build
 
help:
	@echo "A101 PageMaker Build System"
	@echo ""
	@echo "Build Targets:"
	@echo "  all           - Build default presentation (same as build)"
	@echo "  build         - Build PDF presentation from Org file"
	@echo "  $(TYP)        - Generate Typst file from Org"
	@echo "  $(PDF)        - Build PDF from Org (with sanitization)"
	@echo "  ir            - Generate intermediate JSON representation"
	@echo "  watch         - Watch for changes and rebuild automatically"
	@echo ""
	@echo "Development Targets:"
	@echo "  clean         - Remove generated files"
	@echo "  assets        - Check that all referenced assets exist"
	@echo "  check         - Run assets check then build"
	@echo "  debug-overlay - Build debug overlay example"
	@echo ""
	@echo "Testing Targets:"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-verbose  - Run tests with maximum verbosity"
	@echo "  test-coverage - Run tests with coverage report"
	@echo ""
	@echo "Variables:"
	@echo "  ORG=$(ORG)"
	@echo "  TYP=$(TYP)"
	@echo "  PDF=$(PDF)"
	@echo "  HTML=$(HTML)"
	@echo "  TYPST=$(TYPST)"
	@echo "  PY=$(PY)"
 
build: $(PDF)
	@echo 'Build complete -> $(PDF)'
 
$(TYP): $(ORG)
	PYTHONPATH=../src $(PY) -m pagemaker.cli build $(ORG) -o $(TYP) --ir $(IR) --export-dir . --update-html $(HTML)
 
$(PDF): $(ORG)
	PYTHONPATH=../src $(PY) -m pagemaker.cli pdf $(ORG) --export-dir . --pdf-output $(PDF) --sanitize-pdfs


assets:
	@refs=$$(grep -E '^(\\[\\[file:|:PDF:)' $(ORG) | sed -E -e 's/^\\[\\[file:([^]]*)\\]\\].*/\1/' -e 's/^:PDF:[[:space:]]*//'); \
	missing=0; \
	for r in $$refs; do \
	  if [ ! -f "$$r" ]; then echo "Missing asset: $$r"; missing=1; fi; \
	done; \
	if [ $$missing -eq 0 ]; then echo 'All assets present'; else echo 'Asset check failed'; exit 1; fi

ir: $(ORG)
	PYTHONPATH=../src $(PY) -m pagemaker.cli build $(ORG) -o $(TYP) --ir $(IR) --export-dir . --update-html $(HTML)

watch: build
	PYTHONPATH=../src $(PY) -m pagemaker.cli watch $(ORG) --pdf --pdf-output $(PDF) --export-dir .

clean:
	rm -f $(TYP) $(PDF) $(IR)

check: assets build

debug-overlay:
	@echo "Building debug overlay test with custom fonts..."
	cd .. && PYTHONPATH=src $(PY) -m pagemaker.cli pdf examples/debug_overlay.org --export-dir . --pdf-output debug_overlay.pdf --no-clean
	@echo "Debug overlay test complete -> ../debug_overlay.pdf"

# Test targets
.PHONY: test test-unit test-integration test-verbose

test:
	@echo "Running all tests..."
	python -m unittest discover -s ../tests -t .. -v
 
 test-unit:
	@echo "Running unit tests..."
	python -m unittest discover -s ../tests/unit -t .. -v
 
 test-integration: 
	@echo "Running integration tests..."
	python -m unittest discover -s ../tests/integration -t .. -v
 
 test-verbose:
	@echo "Running tests with maximum verbosity..."
	python -m unittest discover -s ../tests -t .. -v -b
 
 test-coverage:
	@echo "Running tests with coverage..."
	python -m coverage run -m unittest discover -s ../tests -t ..
	python -m coverage report
	python -m coverage html

