# pagemaker

Important: This project is in no way affiliated with or related to the old Aldus PageMaker program from the 90s.


A grid-based layout engine for Typst. Includes an optional Org-mode parser that generates Typst code and a CLI.

## Features

### Core Functionality
- **Org-mode to Typst conversion (optional)**: Converts Org documents to Typst
- **Grid-based positioning**: Grid layout (e.g., 12x8) with A1-style areas
- **Element types**: Header, subheader, body text, image, PDF, rectangle
- **Z-order**: Element stacking control
- **Typography**: Fonts and basic theming

### Features
- **PDF embedding**: MuchPDF integration with sanitize/SVG/PNG fallback
- **Rectangles**: Colored overlays with alpha transparency
- **Images**: Fit modes (contain, cover, fill) and captions
- **Debug grid**: Optional grid lines and labels (columns 1..N, rows a..z)
- **Custom fonts**: Integrated support for Manrope and other typography families

### Supported Elements

| Element Type | Description | Properties |
|-------------|-------------|------------|
| `header` | Main headings | Font: Manrope Bold, 24pt |
| `subheader` | Section headings | Font: Manrope SemiBold, 18pt |  
| `body` | Regular text | Font: Manrope Regular |
| `figure` | Images with optional captions | Supports fit modes, captions |
| `pdf` | Vector PDF embedding | Page selection, scaling |
| `svg` | SVG image embedding | Fit: contain; path via `:SVG:` |
| `rectangle` | Colored overlays | Custom colors, alpha transparency |

## Quick Start

### Installation
```bash
# Clone the repository
git clone ssh://gitea@git.mauc.nl:50022/Mauc/pagemaker.git
cd pagemaker

# Ensure you have Python 3.x and Typst installed
pip install -r requirements.txt  # (if requirements exist)
typst --version
```

### Installation (Editable)
```bash
pip install -e .
# Now 'pagemaker' entry point is available
pagemaker --help
```

### Basic Usage (New Multi-Command CLI)

#### Watch Mode
Continuously rebuild Typst (and optionally PDF) when the source Org file changes.
```
# Rebuild typst on change
pagemaker watch examples/sample.org --export-dir export

# Build PDF on each change, keep intermediate .typ
pagemaker watch examples/sample.org --pdf --no-clean --export-dir export

# Single build (no loop) - useful for tests
pagemaker watch examples/sample.org --once --export-dir export
```
Options:
- `--interval <seconds>`: Polling interval (default 1.0)
- `--pdf`: Also compile PDF each rebuild
- `--pdf-output <file>`: Custom PDF filename
- `--typst-bin <path>`: Path to `typst` binary
- `--no-clean`: Keep the intermediate `.typ` after PDF build
- `--update-html <path>`: Update existing HTML file's page count placeholder
- `--once`: Perform exactly one build then exit
- `--sanitize-pdfs`: Attempt to sanitize PDFs; if Typst compile still fails, auto-fallback to SVG or PNG for the requested page

```bash
# Build Typst from Org (org -> typst)
python -m pagemaker.cli build examples/sample.org -o deck.typ

# Build and produce PDF (cleans .typ by default)
python -m pagemaker.cli pdf examples/sample.org --pdf-output deck.pdf

# Build with PDF sanitize + fallback (qpdf/mutool/gs optional)
python -m pagemaker.cli pdf examples/sample.org --sanitize-pdfs --pdf-output deck.pdf

# Emit IR JSON to stdout
python -m pagemaker.cli ir examples/sample.org > ir.json

# Validate IR (non-zero exit on error)
python -m pagemaker.cli validate examples/sample.org
```


Manual Typst compile (if you only produced .typ):
```bash
typst compile --root . --font-path assets/fonts --font-path assets/fonts/static export/deck.typ export/deck.pdf
```

Or use the Makefile targets:
```bash
make debug-overlay  # Build debug example
```

#### Asset Path Semantics
When exporting into an `export/` directory, any relative asset references in the Org file like:
```
[[file:assets/diagram.png]]
:PDF: assets/spec.pdf
:SVG: assets/graphics/logo.svg
```
are automatically rewritten so the generated `deck.typ` can reside in `export/` while still finding the assets in the project root. You can also use absolute paths if preferred.

### Example Org File
```org
#+TITLE: My Presentation
#+PAGESIZE: A4
#+ORIENTATION: landscape
#+GRID: 12x8
#+GRID_DEBUG: false

* Introduction Slide
:PROPERTIES:
:ID: intro_slide
:END:

** Main Title
:PROPERTIES:
:TYPE: header
:AREA: B2,I3
:Z: 100
:END:
Welcome to pagemaker

** Background Rectangle
:PROPERTIES:
:TYPE: rectangle
:AREA: A1,L8
:COLOR: #3498db
:ALPHA: 0.2
:Z: 10
:END:

** Demo Image
:PROPERTIES:
:TYPE: figure
:AREA: H3,K6
:FIT: contain
:Z: 50
:END:
[[file:assets/test-images/landscapes/landscape-1.jpg]]
```

## Directory Structure

```
pagemaker/
├── src/                    # Source code
│   ├── pagemaker/         # Package (parser, generator, CLI)
├── bin/                   # Build tools and scripts
│   ├── Makefile          # Build automation
│   └── debug_test_fonts.sh
├── assets/               # Fonts and test resources
│   ├── fonts/           # Manrope and other typography
│   ├── test-images/     # Sample images for testing
│   └── test-pdfs/       # Sample PDFs for testing
├── examples/            # Example Org files and outputs
├── tests/              # Test suite
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── fixtures/      # Test data
└── docs/              # Documentation
```

## Configuration

### Page Setup
- **PAGESIZE**: A4, A3, A2, A1, A5
- **ORIENTATION**: landscape, portrait
- **GRID**: Custom grid dimensions (e.g., 12x8, 16x9)
- **GRID_DEBUG**: Show/hide debug grid lines

### Element Properties

#### Validation Rules
The `validate` subcommand parses Org -> IR, then enforces structural rules.
Errors (fail the build):
- Duplicate page IDs
- Duplicate element IDs
- Rectangle alpha outside 0.0–1.0
- Area issues: non-positive dimensions or exceeding page grid bounds (when grid + area fully specified)

Warnings (reported but do not fail):
- Unknown element types (fallback treatment may change later)
- Missing figure or PDF asset file (relative path that does not exist when validating)

To escalate missing asset warnings into errors (e.g., for CI pipelines), use:
```
pagemaker validate --strict-assets examples/sample.org
```
This makes missing figure/pdf assets fail validation (non-zero exit code).

Example:
```
pagemaker validate examples/sample.org
```
Exit code 0 means no errors (warnings may still appear).
- **TYPE**: Element type (header, subheader, body, figure, pdf, rectangle)
- **AREA**: A1-style coordinates are preferred (e.g., single cell "B3" or range "A1,C2"). Rows are letters (A=1), columns are numbers. Legacy numeric "x,y,w,h" is still supported.
- **Z**: Stacking order (higher numbers appear on top)
- **COLOR**: Hex color for rectangles (#RRGGBB)
- **ALPHA**: Transparency (0.0 = transparent, 1.0 = opaque)
- **FIT**: Image fitting (contain, cover, fill)

## Tooling

Optional external tools improve PDF handling when using `--sanitize-pdfs`:
- `qpdf`: Repairs and normalizes PDF structure (stream recompress, object streams)
- `mutool` (MuPDF): Cleans PDFs and renders SVG/PNG fallbacks
- `gs` (Ghostscript): Alternate PDF distillation and PNG fallback rendering

The CLI automatically detects these tools. If unavailable, related stages are skipped.

## Advanced Usage

### Custom Fonts
The system uses `--font-path` to include custom fonts:
```bash
typst compile --font-path assets/fonts --font-path assets/fonts/static input.typ output.pdf
```

### Colored Rectangles
Create transparent overlays and design elements:
```org
** Background Accent
:PROPERTIES:
:TYPE: rectangle
:AREA: B2,I6
:COLOR: #FF6B6B
:ALPHA: 0.3
:Z: 10
:END:
```

### Vector PDF Embedding
Include high-quality PDF pages with fallback support:
```org
** Technical Diagram
:PROPERTIES:
:TYPE: pdf
:PDF: assets/technical-drawing.pdf
:PAGE: 2
:SCALE: 1.2
:AREA: D2,I5
:Z: 50
:END:
```
Notes:
- For problematic PDFs with MuchPDF, run the CLI with `--sanitize-pdfs`.
- If sanitization still fails, the first requested page is auto-converted to SVG (preferred) or PNG and embedded as an image.
- Fallback assets are written under `export_dir/assets/pdf-fallbacks/` and linked in the generated Typst.

### SVG Embedding
Embed SVG graphics directly:
```org
** Vector Graphic
:PROPERTIES:
:TYPE: svg
:SVG: assets/test-svgs/test-plan-p11.svg
:AREA: C2,J6
:END:
```
- Paths are treated like other assets and adjusted relative to the export directory.
- Fit defaults to contain within the target area.

## A1 AREA Notation

- Rows are letters A..Z, then AA, AB, etc. (case-insensitive). A maps to row 1.
- Columns are numbers starting at 1.
- Single cell: "B3" -> [x=3, y=2, w=1, h=1].
- Range: "A1,C2" -> inclusive rectangle normalized to top-left/bottom-right yielding [x=1, y=1, w=2, h=3].
- Reverse ranges like "C2,A1" are normalized the same as "A1,C2".
- Legacy format "x,y,w,h" remains supported for backward compatibility.
- Debug grid labels: columns show 1..N at top; rows show a..z at left (rows > 26 currently fall back to numeric display).

## Development

### Running Tests
```bash
make test
# or
python -m unittest discover tests -v
```

- The suite includes an optional PDF compile test that runs `pagemaker pdf` end-to-end and compiles via Typst. It automatically skips if `typst` or the `@preview/muchpdf` package are unavailable on your system.

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Created for building Typst-based slide decks from Org-mode.

---

*For more detailed documentation, examples, and advanced usage patterns, see the `docs/` directory and `examples/` folder.*