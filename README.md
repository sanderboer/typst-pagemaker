# A101 PageMaker

A powerful presentation generator that converts Org-mode documents into professional Typst presentations with grid-based layouts, custom fonts, and advanced features.

## Features

### Core Functionality
- **Org-mode to Typst conversion**: Seamless conversion of structured Org documents
- **Grid-based positioning**: Precise element placement using customizable grids (e.g., 12x8)
- **Multiple element types**: Headers, subheaders, body text, images, PDFs, and colored rectangles
- **Z-order layering**: Complete control over element stacking and overlay relationships
- **Custom typography**: Built-in support for modern fonts with configurable themes

### Advanced Features
- **Vector PDF embedding**: High-quality PDF inclusion with muchpdf integration
- **Transparent rectangles**: Colored overlays with alpha transparency for design accents
- **Image handling**: Flexible image fitting (contain, cover, fill) with captions
- **Debug grid**: Optional grid lines for precise layout debugging
- **Custom fonts**: Integrated support for Manrope and other typography families

### Supported Elements

| Element Type | Description | Properties |
|-------------|-------------|------------|
| `header` | Main headings | Font: Manrope Bold, 24pt |
| `subheader` | Section headings | Font: Manrope SemiBold, 18pt |  
| `body` | Regular text | Font: Manrope Regular |
| `figure` | Images with optional captions | Supports fit modes, captions |
| `pdf` | Vector PDF embedding | Page selection, scaling |
| `rectangle` | Colored overlays | Custom colors, alpha transparency |

## Quick Start

### Installation
```bash
# Clone the repository
git clone ssh://gitea@git.mauc.nl:50022/Mauc/A101-pagemaker.git
cd A101-pagemaker

# Ensure you have Python 3.x and Typst installed
pip install -r requirements.txt  # (if requirements exist)
typst --version
```

### Basic Usage (New Multi-Command CLI)
```bash
# Build Typst from Org (org -> typst)
python -m pagemaker.cli build examples/sample.org -o deck.typ

# Build and produce PDF (cleans .typ by default)
python -m pagemaker.cli pdf examples/sample.org --pdf-output deck.pdf

# Emit IR JSON to stdout
python -m pagemaker.cli ir examples/sample.org > ir.json

# Validate IR (non-zero exit on error)
python -m pagemaker.cli validate examples/sample.org
```

Legacy single-script usage (still supported, will be deprecated):

```bash
# Generate Typst from Org file (artifacts go into ./export by default)
python3 src/gen_typst.py examples/sample.org

# Explicit output filename relative to export dir
python3 src/gen_typst.py examples/sample.org -o deck.typ

# Specify a different export directory
python3 src/gen_typst.py examples/sample.org --export-dir build

# Directly generate PDF (auto-compiles with fonts; cleans .typ by default)
python3 src/gen_typst.py examples/sample.org --pdf

# Keep the intermediate Typst file alongside the PDF
python3 src/gen_typst.py examples/sample.org --pdf --no-clean

# Custom PDF output name
python3 src/gen_typst.py examples/sample.org --pdf --pdf-output presentation.pdf

# Specify custom typst binary path
python3 src/gen_typst.py examples/sample.org --pdf --typst-bin /usr/local/bin/typst

# Manual compile to PDF (if you only produced .typ)
typst compile --font-path assets/fonts --font-path assets/fonts/static export/deck.typ export/deck.pdf

# Or use the Makefile targets
make debug-overlay  # Build debug example
```

#### Asset Path Semantics
When exporting into an `export/` directory, any relative asset references in the Org file like:
```
[[file:assets/diagram.png]]
:PDF: assets/spec.pdf
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
:AREA: 2,2,8,2
:Z: 100
:END:
Welcome to A101 PageMaker

** Background Rectangle
:PROPERTIES:
:TYPE: rectangle
:AREA: 1,1,12,8
:COLOR: #3498db
:ALPHA: 0.2
:Z: 10
:END:

** Demo Image
:PROPERTIES:
:TYPE: figure
:AREA: 8,3,4,4
:FIT: contain
:Z: 50
:END:
[[file:assets/test-images/landscapes/landscape-1.jpg]]
```

## Directory Structure

```
A101-pagemaker/
├── src/                    # Source code
│   └── gen_typst.py       # Main conversion script
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
- **TYPE**: Element type (header, subheader, body, figure, pdf, rectangle)
- **AREA**: Grid position and size (x, y, width, height)
- **Z**: Stacking order (higher numbers appear on top)
- **COLOR**: Hex color for rectangles (#RRGGBB)
- **ALPHA**: Transparency (0.0 = transparent, 1.0 = opaque)
- **FIT**: Image fitting (contain, cover, fill)

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
:AREA: 2,2,8,5
:COLOR: #FF6B6B
:ALPHA: 0.3
:Z: 10
:END:
```

### Vector PDF Embedding
Include high-quality PDF pages:
```org
** Technical Diagram
:PROPERTIES:
:TYPE: pdf
:PDF: assets/technical-drawing.pdf
:PAGE: 2
:SCALE: 1.2
:AREA: 4,2,6,4
:Z: 50
:END:
```

## Development

### Running Tests
```bash
cd tests
python3 -m pytest unit/
python3 -m pytest integration/
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Created as part of the A101 project series.

---

*For more detailed documentation, examples, and advanced usage patterns, see the `docs/` directory and `examples/` folder.*