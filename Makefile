# A101 PageMaker - Root Makefile
# This delegates to the actual build system in bin/

.PHONY: all build clean test debug-overlay help install-dev lint version-info

all:
	@$(MAKE) -C bin build

build:
	@$(MAKE) -C bin build

clean:
	@$(MAKE) -C bin clean
	@rm -f *.typ *.pdf *.json

test:
	@$(MAKE) -C bin test

debug-overlay:
	@$(MAKE) -C bin debug-overlay

help:
	@echo "A101 PageMaker - Org-mode to Typst Presentation Generator"
	@echo ""
	@echo "Build Targets:"
	@echo "  all           - Build default presentation"
	@echo "  build         - Build presentation"
	@echo "  clean         - Clean generated files"
	@echo "  test          - Run test suite"
	@echo "  debug-overlay - Build debug overlay example"
	@echo ""
	@echo "Development Targets:"
	@echo "  install-dev   - Install package in development mode"
	@echo "  lint          - Run code quality checks"
	@echo "  version-info  - Show current version and git status"
	@echo "  help          - Show this help"
	@echo ""
	@echo "Note: PyPI publishing is handled automatically via GitHub Actions"
	@echo "      when version is bumped in pyproject.toml and pushed to main."
	@echo ""
	@echo "For more build options, see bin/Makefile"

install-dev:
	pip install -e .
	@echo ""
	@echo "Package installed in development mode. Test with:"
	@echo "  pagemaker --help"

lint:
	@echo "Running basic code quality checks..."
	@python -m py_compile src/pagemaker/*.py
	@echo "✓ Python files compile successfully"
	@if command -v ruff >/dev/null 2>&1; then \
		echo "Running ruff checks..."; \
		ruff check src/; \
	else \
		echo "⚠ ruff not installed - install with: pip install ruff"; \
	fi

version-info:
	@echo "Current version info:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@grep "version = " pyproject.toml
	@echo ""
	@echo "Git status:"
	@git status --porcelain || echo "Not a git repository"
	@echo ""
	@echo "Recent commits:"
	@git log --oneline -3 2>/dev/null || echo "No git history found"
	@echo ""
	@echo "To publish new version:"
	@echo "  1. Update version in pyproject.toml"
	@echo "  2. Commit and push to GitHub"
	@echo "  3. GitHub Actions will auto-publish to PyPI"