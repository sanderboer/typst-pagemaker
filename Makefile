# A101 PageMaker - Root Makefile
# This delegates to the actual build system in bin/

.PHONY: all build clean test debug-overlay help

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
	@echo "Available targets:"
	@echo "  all           - Build default presentation"
	@echo "  build         - Build presentation"
	@echo "  clean         - Clean generated files"
	@echo "  test          - Run test suite"
	@echo "  debug-overlay - Build debug overlay example"
	@echo "  help          - Show this help"
	@echo ""
	@echo "For more build options, see bin/Makefile"