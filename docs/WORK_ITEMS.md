# Pagemaker Work Items & Roadmap

**Document Version**: 1.0  
**Last Updated**: 2025-11-09  
**Status**: Active Development  

---

## Executive Summary

This document tracks outstanding work items, known issues, and future enhancements for the Pagemaker project. Items are organized by feature area with priority levels, complexity estimates, and clear acceptance criteria.

### Quick Status
- **Overall Progress**: ~78% complete (7/9 major milestones done)
- **Tests Passing**: 245/247 (98.9%) - 2 font-related failures
- **Recent Completion**: M7 (HTML Export Core) ✅
- **Next Major Milestone**: M7.5 (HTML Grid Layout) - 2 weeks estimated

---

## 🔴 Critical Issues

### C1: Font Discovery Test Failures
**Priority**: High  
**Status**: ❌ Failing  
**Affected Tests**:
- `test_fonts_helpers.py::test_discover_fonts_in_path_groups_by_family`
- `test_fonts_helpers.py::test_collect_real_font_names_from_ttf`

**Problem**: Tests expect font directory at `test/assets/fonts/` but it doesn't exist.

**Root Cause**: Test setup references incorrect path
```python
self.test_fonts_dir = self.repo_root / 'test' / 'assets' / 'fonts'
```

**Actual Path**: `examples/assets/fonts/`

**Fix Required**:
1. **Option A**: Create `test/assets/fonts/` directory with minimal test fonts (preferred)
   - Create directory structure
   - Copy 2-3 minimal test fonts (e.g., Inter, Manrope)
   - Keep test fonts small (<100KB total)
   
2. **Option B**: Update test to use `examples/assets/fonts/`
   - Modify `test_fonts_helpers.py` line 29
   - Update test expectations to match actual font families in examples
   - Risk: Tests depend on example files (coupling)

**Complexity**: Low (30 minutes)  
**Files to Modify**: 
- `tests/unit/test_fonts_helpers.py` (lines 29-46)
- OR create `test/assets/fonts/` directory structure

**Acceptance Criteria**:
- [ ] Both font discovery tests pass
- [ ] Test suite reaches 247/247 passing (100%)
- [ ] Font discovery logic verified working
- [ ] Tests don't depend on example files

**Related Code**:
- `src/pagemaker/fonts.py` - Font discovery implementation
- `src/pagemaker/utils/font_discovery.py` - Font path utilities

---

## 📋 Feature Work Items

### F1: HTML Grid Layout System (M7.5)
**Priority**: Critical  
**Status**: 🔄 Planned  
**Milestone**: M7.5  
**Duration**: 2 weeks  
**Complexity**: High  

**Problem**: HTML export currently renders content sequentially (top-to-bottom flow), ignoring pagemaker's core grid-based layout system (`:AREA:` properties). This breaks the fundamental slide presentation paradigm.

**Current Behavior**:
- HTML flows content like a document (semantic, accessible)
- `:AREA:` grid coordinates ignored
- No page separation or navigation
- Output suitable for reading but not presenting

**Required Behavior**:
- Each org-mode page = full-viewport HTML slide
- CSS Grid positioning matches PDF layout
- Page-based navigation (keyboard + UI)
- Responsive scaling to viewport size

**Implementation Plan**:

#### F1.1: CSS Grid Implementation
**Tasks**:
- [ ] Parse `:AREA:` coordinates from IR (format: `x,y,w,h`)
- [ ] Convert to CSS Grid syntax: `grid-column: x / (x+w); grid-row: y / (y+h)`
- [ ] Generate CSS Grid container for each page:
  ```css
  .page-container {
    display: grid;
    grid-template-columns: repeat(12, 1fr);  /* from #+GRID: 12,8 */
    grid-template-rows: repeat(8, 1fr);
    width: 100vw;
    height: 100vh;
    overflow: hidden;
  }
  ```
- [ ] Wrap each element in grid-positioned div:
  ```html
  <div class="grid-item" style="grid-area: 1 / 2 / 5 / 7;">
    <p>Content here</p>
  </div>
  ```

**Files to Modify**:
- `src/pagemaker/generation/html_generator.py` (lines 100-300)
  - Extract `:AREA:` from each element
  - Generate grid container markup
  - Add inline CSS for grid positioning

#### F1.2: Page-Based Rendering
**Tasks**:
- [ ] Wrap each page in container: `<div class="page" data-page="1">`
- [ ] Hide all pages except current: `.page { display: none; } .page.active { display: grid; }`
- [ ] Extract page count from IR
- [ ] Generate page metadata in HTML

**Files to Modify**:
- `src/pagemaker/generation/html_generator.py` (page wrapper logic)

#### F1.3: Navigation UI
**Tasks**:
- [ ] Keyboard navigation:
  - Arrow keys: Next/Previous page
  - Page Up/Down: Next/Previous page
  - Home/End: First/Last page
- [ ] UI controls:
  - Previous/Next buttons (bottom corners)
  - Page counter: "2 / 10" (bottom center)
  - Optional: Thumbnail sidebar
- [ ] URL hash navigation: `#page-2`
- [ ] Scroll lock (prevent accidental scrolling between pages)

**Implementation**:
- [ ] Create `src/pagemaker/templates/navigation.js` (standalone JavaScript)
- [ ] Inject JavaScript into HTML during postprocessing
- [ ] Add CSS for navigation UI buttons

**Files to Create**:
- `src/pagemaker/templates/navigation.js` (~150 lines)
- `src/pagemaker/templates/grid-layout.css` (~100 lines)

#### F1.4: Responsive Scaling
**Tasks**:
- [ ] Detect viewport aspect ratio vs design aspect ratio
- [ ] Scale grid proportionally to fit viewport
- [ ] Maintain content readability (min font sizes)
- [ ] Optional: Breakpoints for mobile/tablet

**CSS Approach**:
```css
.page-container {
  /* Use CSS transforms to scale to viewport */
  transform: scale(var(--page-scale));
  transform-origin: top left;
}
```

**JavaScript**:
- [ ] Calculate scale factor on load and resize
- [ ] Update CSS custom property: `--page-scale`

#### F1.5: Testing
**Tests Required**:
- [ ] Unit tests for `:AREA:` → CSS Grid conversion
- [ ] Integration test: compile .org with grid layout
- [ ] Visual regression test: PDF vs HTML layout parity
- [ ] Browser testing: Chrome, Firefox, Safari, Edge
- [ ] Keyboard navigation tests
- [ ] Responsive scaling tests (various viewport sizes)

**Test Files**:
- `tests/unit/test_html_grid_positioning.py` (new, ~10 tests)
- `tests/integration/test_html_grid_layout_cli.py` (new, ~5 tests)

**Acceptance Criteria**:
- [ ] HTML pages render as full-viewport slides
- [ ] Element positioning matches PDF output (visual parity)
- [ ] Navigation between pages works (keyboard/UI)
- [ ] Grid scales proportionally to viewport
- [ ] `examples/alignment_matrix_demo.org` renders correctly in HTML
- [ ] All existing tests still pass (zero regressions)
- [ ] New tests: 15+ tests for grid layout functionality

**Related Issues**: 
- Addresses Issue #2 from M7 Known Issues
- Unblocks M8 (asset management may need grid-aware paths)

**Estimated Effort**: 2 weeks (80 hours)
- Week 1: CSS Grid implementation + page rendering
- Week 2: Navigation UI + responsive scaling + testing

---

### F2: Font Rendering & Emphasis Support
**Priority**: Medium  
**Status**: ✅ Mostly Working, Needs Testing  
**Complexity**: Low-Medium  

**Current Status**:
- ✅ Emphasis markup parsing working (`*bold*`, `/italic/`)
- ✅ Converts to Typst: `#strong[bold]`, `#emph[italic]`
- ✅ Font weight support: regular, medium, semibold, bold, extrabold
- ✅ Style support: italic
- ⚠️ Unknown: Interaction with custom fonts in HTML export
- ⚠️ Unknown: Underline support (not implemented)

**Code Locations**:
- `src/pagemaker/utils/typst_helpers.py::process_org_emphasis()` (lines 272-290)
- `src/pagemaker/generator.py::process_org_emphasis()` (lines 585-603)
- Weight constants: `src/pagemaker/generation/core.py` (lines 21-23)

**Known Working**:
- Bold/italic in PDF export
- Term bolding in description lists (uses `#strong`)
- Link descriptions with emphasis markup
- Text styling with font weights

**Work Items**:

#### F2.1: HTML Emphasis Rendering Verification
**Tasks**:
- [ ] Test bold/italic rendering in HTML export
- [ ] Verify `#strong` and `#emph` convert correctly to `<strong>` and `<em>`
- [ ] Test emphasis within links, headings, lists
- [ ] Test nested emphasis (if supported by org-mode)

**Test File**: `tests/integration/test_html_emphasis_rendering.py` (new)

#### F2.2: Underline Support
**Status**: Not implemented  
**Tasks**:
- [ ] Add org-mode underline parsing: `_underline_`
- [ ] Convert to Typst: `#underline[text]`
- [ ] Update `process_org_emphasis()` regex patterns
- [ ] Add tests for underline markup

**Files to Modify**:
- `src/pagemaker/utils/typst_helpers.py` (lines 286-289)
- `tests/unit/test_emphasis_markup.py` (new file)

#### F2.3: Custom Font Bold/Italic Variants
**Status**: Partially implemented  
**Problem**: Font discovery detects variants but unclear if all variants properly applied

**Tasks**:
- [ ] Verify font variant detection logic works correctly
- [ ] Test custom fonts with multiple variants (Light, Regular, Bold, Italic, Bold Italic)
- [ ] Ensure Typst weight parameter maps correctly to font files
- [ ] Document font variant requirements in README

**Code Location**: `src/pagemaker/utils/font_discovery.py` (lines 355-357)

**Acceptance Criteria**:
- [ ] Bold/italic rendering verified in both PDF and HTML
- [ ] Underline support added (if desired)
- [ ] 10+ tests covering emphasis edge cases
- [ ] Documentation updated with emphasis markup examples

**Estimated Effort**: 3 days

---

### F3: Table Rendering Improvements
**Priority**: Medium  
**Status**: ✅ Working (PDF), ⚠️ Simplified (HTML)  
**Complexity**: Medium  

**Current Status**:
- ✅ Org-mode table parsing works (`TABLE_LINE_RE`, `TABLE_SEP_RE`)
- ✅ PDF table rendering full-featured:
  - Auto-sized columns
  - Header row detection (bolded)
  - Horizontal rules (separators)
  - Gutter spacing
  - Text alignment within cells
- ⚠️ HTML table rendering simplified:
  - Currently just a placeholder comment: `// (table rendering simplified in HTML)`
  - Typst `#table()` likely converts to HTML `<table>`, but not verified

**Code Locations**:
- `src/pagemaker/parser.py::_try_parse_table()` (lines 230-278)
- `src/pagemaker/table_render.py::render_table_block()` (main implementation)
- `src/pagemaker/generation/html_generator.py::_generate_table()` (lines 276-280, simplified)

**Work Items**:

#### F3.1: HTML Table Rendering Implementation
**Tasks**:
- [ ] Remove placeholder comment in `html_generator.py`
- [ ] Implement proper table generation for HTML export:
  - [ ] Convert to Typst `#table()` (same as PDF path)
  - [ ] OR generate semantic HTML `<table>` directly
  - [ ] Preserve header rows (use `<thead>`)
  - [ ] Preserve separators (use borders/styling)
- [ ] Test Typst → HTML table conversion
- [ ] Add CSS styling for tables in HTML export

**Decision Point**: Use Typst's table → HTML conversion vs. direct HTML generation
- **Option A**: Use `table_render.py` logic (consistent with PDF)
  - Pros: Reuses existing code, consistent behavior
  - Cons: Depends on Typst HTML table support
- **Option B**: Direct HTML `<table>` generation in `html_generator.py`
  - Pros: Full control, semantic HTML
  - Cons: Code duplication, maintenance burden

**Files to Modify**:
- `src/pagemaker/generation/html_generator.py` (lines 276-280)

#### F3.2: Advanced Table Features
**Status**: Not implemented  
**Potential Enhancements**:
- [ ] Column alignment specifications (left/center/right)
- [ ] Column width hints
- [ ] Cell spanning (colspan/rowspan)
- [ ] Nested tables
- [ ] Table captions
- [ ] Alternating row colors (zebra striping)

**Priority**: Low (nice-to-have enhancements)

#### F3.3: Table Testing
**Current Tests**:
- ✅ Integration test: `test_tables_cli.py` (PDF compilation)
- ✅ Unit tests: `test_tables_parser.py`, `test_tables_generator.py`

**Missing Tests**:
- [ ] HTML table rendering tests
- [ ] Table with emphasis markup in cells
- [ ] Complex table layouts (many rows/columns)
- [ ] Edge cases: empty cells, single-cell tables

**Acceptance Criteria**:
- [ ] HTML tables render correctly (not just placeholder)
- [ ] Header rows styled appropriately in HTML
- [ ] Separators render as borders or spacing
- [ ] Tables responsive in HTML (wrap or scroll on mobile)
- [ ] 5+ new tests for HTML table rendering
- [ ] Example file: `examples/table_demo.org`

**Estimated Effort**: 1 week

---

### F4: Media Sizing & Alignment
**Priority**: Low  
**Status**: ✅ Complete (PDF), ⚠️ Needs Verification (HTML)  
**Complexity**: Low  

**Current Status**:
- ✅ **M1-M3 Complete**: Unified media sizing & alignment system
- ✅ PDF rendering: All media types (image, SVG, PDF) work correctly
- ✅ Cover/Contain/Stretch modes working
- ✅ Alignment-based cropping implemented
- ✅ 56 tests covering media sizing/alignment
- ⚠️ HTML: Base64 data URI embedding works, but grid positioning not yet implemented (F1)

**Code Locations**:
- `src/pagemaker/generation/media_sizing.py` (355 lines, 3 size providers)
- `src/pagemaker/generation/media_renderer.py` (525 lines, 3 render strategies)
- `src/pagemaker/generator.py::_compute_media_drawn_and_offsets()` (alignment math)

**Work Items**:

#### F4.1: HTML Media Alignment Verification
**Tasks**:
- [ ] Once F1 (Grid Layout) complete, verify media alignment in HTML
- [ ] Test cover/contain/stretch modes in HTML output
- [ ] Test alignment properties (`:ALIGN:`, `:VALIGN:`) in HTML
- [ ] Ensure media fits grid cells correctly

**Blocked By**: F1 (HTML Grid Layout)

#### F4.2: Media Aspect Ratio Preservation
**Status**: Working, needs verification  
**Tasks**:
- [ ] Verify aspect ratios preserved in HTML (not distorted)
- [ ] Test various aspect ratios: 16:9, 4:3, 1:1, 2:1
- [ ] Test portrait vs landscape orientations

#### F4.3: Media Performance Optimization
**Status**: Good, can be improved  
**Potential Enhancements**:
- [ ] Cache size provider results (already done per render pass)
- [ ] Lazy loading for images in HTML (browser-native `loading="lazy"`)
- [ ] Responsive images: multiple resolutions for different viewports
- [ ] Image compression/optimization pipeline

**Acceptance Criteria**:
- [ ] Media alignment in HTML matches PDF output
- [ ] Cover/contain/stretch work in HTML grid layout
- [ ] Aspect ratios preserved in all cases
- [ ] No visual distortion of images
- [ ] Performance acceptable for 50+ images per document

**Estimated Effort**: 3 days (mostly testing)

---

### F5: PDF Embedding & Processing
**Priority**: Low  
**Status**: ✅ Working (native Typst), 🔄 Deprecation Pending (M5)  
**Complexity**: Low  

**Current Status**:
- ✅ Native Typst `image()` embedding for PDFs (MuchPDF removed)
- ✅ PDF sizing probes work correctly (72 pt/in standard)
- ✅ Multi-page PDF support (`:PAGE:` parameter)
- ✅ Box preference parameter (`:BOX:` - media/crop/trim/bleed/art)
- ⏸️ Legacy sanitization pipeline still present but deprecated

**Code Locations**:
- `src/pagemaker/generation/pdf_processor.py` - PDF utilities
- `src/pagemaker/cli.py` - Sanitization functions (to be moved in M5)

**Work Items** (M5 - Deferred):

#### F5.1: Deprecate PDF Sanitization Pipeline
**Tasks**:
- [ ] Move sanitization functions from `cli.py` to `pdf_processor.py`
- [ ] Add `--legacy-pdf-fallbacks` flag (replaces `--sanitize-pdfs`)
- [ ] Default: fallbacks disabled
- [ ] Emit `DeprecationWarning` when flag used
- [ ] Document external preprocessing alternatives (Ghostscript, pdf2svg)

**Files to Move**:
- `_make_sanitized_copy()` → `pdf_processor.py`
- `_convert_pdf_to_svg()` → `pdf_processor.py`
- `_convert_pdf_to_png()` → `pdf_processor.py`
- `_apply_pdf_sanitized_copies()` → `pdf_processor.py`
- `_apply_pdf_svg_fallbacks()` → `pdf_processor.py`

#### F5.2: PDF Processing Documentation
**Tasks**:
- [ ] Document when PDF embedding fails (common causes)
- [ ] Provide troubleshooting guide
- [ ] Recommend external tools for PDF repair
- [ ] Example workflow: problematic PDF → Ghostscript → repaired PDF

**Acceptance Criteria**:
- [ ] Sanitization code moved to proper module
- [ ] Feature flag controls activation
- [ ] Deprecation warning clear and actionable
- [ ] Documentation explains migration path
- [ ] Tests updated for new flag

**Estimated Effort**: 1 week  
**Priority**: Low (deferred - not blocking other work)

---

## 🚀 Major Milestones

### M7.5: HTML Grid Layout (Current Focus)
**Status**: 🔄 Planned  
**Duration**: 2 weeks  
**Priority**: Critical  

See **F1: HTML Grid Layout System** above for full details.

**Blockers**: None (ready to start)  
**Dependencies**: M7 complete ✅

---

### M8: HTML Asset Management
**Status**: ⏸️ Pending  
**Duration**: 1 week  
**Priority**: High  
**Blocked By**: M7.5 (optional - can start in parallel)

**Goal**: Portable, self-contained HTML bundles with embedded assets

**Overview**:
Parse generated HTML to identify linked assets (images, SVGs, fonts, CSS), copy them to `export/<basename>/assets/`, and rewrite HTML paths to be relative.

**Current Status**:
- HTML already uses base64 data URIs for media (inline embedding)
- May not need full asset copying if everything is inline
- Need to investigate: fonts, CSS, JavaScript

**Tasks**:
- [ ] Analyze Typst HTML output structure
- [ ] Identify external asset references (if any)
- [ ] Implement asset detection function
- [ ] Implement asset copying function
- [ ] Implement path rewriting function
- [ ] Test portability (move directory, verify works)

**Acceptance Criteria**:
- [ ] HTML bundle is fully portable (no external dependencies)
- [ ] Assets directory contains all referenced files
- [ ] Opening `index.html` in browser works offline
- [ ] No broken asset links (404s)
- [ ] Watch mode updates assets correctly

**Estimated Effort**: 1 week

See `docs/update_plan.md` M8 section for full specification.

---

### M9: HTML Export Polish
**Status**: ⏸️ Pending  
**Duration**: 1 week  
**Priority**: Medium  
**Blocked By**: M7.5, M8

**Goal**: UX improvements, advanced features, comprehensive documentation

**Key Features**:
- [ ] `--html-only` flag (skip PDF compilation)
- [ ] Multi-page document navigation UI
- [ ] HTML metadata injection (title, author, date)
- [ ] Performance optimizations (asset caching)
- [ ] Error handling improvements
- [ ] Comprehensive documentation

**Acceptance Criteria**:
- [ ] All HTML export features documented
- [ ] 10+ integration tests
- [ ] Example .org file demonstrates HTML workflow
- [ ] Cross-browser compatibility verified

**Estimated Effort**: 1 week

See `docs/update_plan.md` M9 section for full specification.

---

### M5: PDF Pipeline Deprecations
**Status**: ⏸️ Deferred  
**Duration**: 1 week  
**Priority**: Low  

See **F5: PDF Embedding & Processing** above for details.

**Reason for Deferral**: Not blocking any other work, low user impact (sanitization rarely needed with native Typst embedding).

---

## 🐛 Known Issues

### Issue 1: HTML Export Directory Structure
**Status**: ⚠️ Minor Issue  
**Priority**: Medium  

**Problem**: HTML exports to `export/deck/index.html` with hardcoded "deck" directory name.

**Expected**: HTML should export to `export/<basename>/index.html`

**Example**:
- Input: `myfile.org`
- Current: `export/deck/index.html` ❌
- Expected: `export/myfile/index.html` ✅

**Fix**:
- [ ] Update output path generation to use source file basename
- [ ] Search for "deck" hardcode in `html_generator.py` or CLI logic
- [ ] Update path construction to use `Path(basename).stem`

**Files to Check**:
- `src/pagemaker/generation/html_generator.py`
- `src/pagemaker/cli.py` (HTML compilation functions)

**Complexity**: Low (30 minutes)

---

### Issue 2: HTML Grid System Not Implemented
**Status**: 🔄 Tracked as F1  
**Priority**: Critical  

See **F1: HTML Grid Layout System** above - this is a major feature, not a bug.

---

### Issue 3: CLI Redesign Needed
**Status**: 💡 Enhancement  
**Priority**: Low  

**Problem**: Current CLI is unintuitive:
- Must use `pagemaker pdf file.org --html` to get HTML (confusing)
- No short flags (`-w`, `-p`, `-H`)
- Rigid subcommand structure

**Proposed Improvement**:
```bash
# Current (awkward)
pagemaker pdf myfile.org --html

# Proposed (intuitive)
pagemaker myfile.org --html
pagemaker myfile.org -H
pagemaker myfile.org -wpH  # watch + PDF + HTML
```

**Benefits**:
- More intuitive UX
- Flexible flag combinations
- Shorter commands
- Better discoverability

**Complexity**: Medium (ArgumentParser refactor)  
**Estimated Effort**: 1 week  

**Implementation Plan**: See `docs/update_plan.md` M7 Issue #3 for full specification.

**Priority**: Low (UX improvement, not blocking features)

---

## 📊 Testing Gaps

### T1: HTML Export Test Coverage
**Current**: 5 tests in `test_html_export_cli.py`  
**Target**: 20+ tests  

**Missing Test Areas**:
- [ ] HTML grid layout (blocked by F1)
- [ ] HTML table rendering
- [ ] HTML emphasis markup
- [ ] HTML media alignment
- [ ] Multi-page HTML navigation
- [ ] Responsive scaling
- [ ] Browser compatibility
- [ ] Accessibility (screen readers, keyboard nav)

**Priority**: High (critical for M7.5 completion)

---

### T2: Font Discovery Tests
**Current**: 2 failing tests  
**Target**: 2 passing + 5 additional edge case tests  

**Missing Tests**:
- [ ] Font variant detection (Bold, Italic, Bold Italic)
- [ ] Multiple font directories
- [ ] Missing font handling
- [ ] Font name conflicts
- [ ] Non-TTF font formats (OTF, WOFF)

**Priority**: High (blocking 100% test pass rate)

---

### T3: Edge Case Coverage
**Areas Needing More Tests**:
- [ ] Empty documents (no content)
- [ ] Very large documents (100+ pages, 500+ images)
- [ ] Malformed org-mode syntax
- [ ] Unicode content (CJK characters, emoji, RTL text)
- [ ] Special characters in filenames/paths
- [ ] Network paths / UNC paths (Windows)
- [ ] Symlinked files and directories
- [ ] Read-only output directories (permission errors)

**Priority**: Medium (robustness improvements)

---

## 📖 Documentation Gaps

### D1: HTML Export User Guide
**Status**: Missing  
**Priority**: High (needed for M7.5 release)  

**Required Content**:
- [ ] Getting started guide
- [ ] Feature comparison: PDF vs HTML output
- [ ] Grid layout explanation
- [ ] Navigation UI usage
- [ ] Browser compatibility matrix
- [ ] Troubleshooting section
- [ ] Example workflows

**Target Location**: `README.md` "HTML Export" section (200-300 lines)

---

### D2: Font Configuration Guide
**Status**: Minimal  
**Priority**: Medium  

**Required Content**:
- [ ] How to install custom fonts
- [ ] Font discovery paths
- [ ] Using Google Fonts integration
- [ ] Font variant requirements (Bold, Italic)
- [ ] Troubleshooting font issues
- [ ] Font licensing considerations

**Target Location**: `docs/FONTS.md` (new file)

---

### D3: Advanced Features Guide
**Status**: Missing  
**Priority**: Low  

**Topics**:
- [ ] Master pages and reusable layouts
- [ ] Custom color schemes
- [ ] Advanced grid layouts
- [ ] Media sizing strategies
- [ ] Performance optimization
- [ ] Batch processing workflows

**Target Location**: `docs/ADVANCED.md` (new file)

---

## 🎯 Priority Matrix

### This Week (Critical)
1. **C1**: Fix font discovery tests (2 failing tests → 0)
2. **F1.1**: Start HTML Grid Layout - CSS Grid implementation

### Next 2 Weeks (High Priority)
1. **F1**: Complete HTML Grid Layout (M7.5)
2. **T1**: HTML export test coverage
3. **D1**: HTML export user guide

### Next Month (Medium Priority)
1. **M8**: HTML Asset Management
2. **M9**: HTML Export Polish
3. **F2**: Emphasis rendering verification
4. **F3**: Table rendering improvements

### Future / Backlog (Low Priority)
1. **M5**: PDF Pipeline Deprecations
2. **F5**: PDF sanitization deprecation
3. **Issue 3**: CLI redesign
4. **T3**: Edge case test coverage
5. **D2-D3**: Advanced documentation

---

## 📈 Success Metrics

### Milestone M7.5 Success Criteria
- [ ] HTML grid layout functional in browser
- [ ] Visual parity: HTML output matches PDF layout
- [ ] Navigation UI working (keyboard + buttons)
- [ ] 15+ new tests for grid functionality
- [ ] Test suite: 260/260 passing (100%)
- [ ] Documentation updated (HTML Export guide)

### Overall Project Health
- **Current**: 245/247 tests passing (98.9%)
- **Target**: 260+/260 tests passing (100%)
- **Code Coverage**: >90% on all modules
- **Documentation**: Comprehensive user guides for all features
- **Performance**: <2s compile time for 10-page document

---

## 🔗 Related Documents

### Architecture & Planning
- `docs/update_plan.md` - Complete milestone specifications (M1-M9)
- `docs/architecture/media_rendering.md` - Media system architecture
- `README.md` - User-facing documentation

### Code Locations
- `src/pagemaker/generation/` - Core generation logic
- `src/pagemaker/parser.py` - Org-mode parsing
- `tests/` - Test suite

### Examples
- `examples/` - Working example .org files
- `examples/alignment_matrix_demo.org` - Alignment demonstrations
- `examples/svg_sizing_demo.org` - SVG sizing demonstrations

---

**Document Maintainers**: Update this document as work items are completed or new issues discovered.

**Review Cycle**: Update weekly during active development.
