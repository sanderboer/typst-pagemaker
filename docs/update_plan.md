# Pagemaker Modernization Roadmap

**Document Version**: 2.0  
**Last Updated**: 2025-11-09  
**Status**: Active Development

---

## Executive Summary

This document consolidates all planned improvements for pagemaker's media handling, PDF processing, and code architecture. The roadmap is organized into 6 major milestones spanning approximately 8-10 weeks of development.

### High-Level Goals
1. **Unify Media Embedding**: Single `:FIT:` API for images, SVGs, and PDFs with consistent cover/contain/stretch semantics
2. **Fix Critical Bugs**: SVG sizing fallback bug causing incorrect scaling with alignment
3. **Improve Code Quality**: Extract ~160 lines of duplicated rendering logic into reusable abstractions
4. **Modernize PDF Pipeline**: Complete native Typst embedding, deprecate legacy fallbacks
5. **Enhance Developer Experience**: Clear architecture, comprehensive tests, excellent documentation

### Completed Work
- [x] Native Typst `image()` embedding for PDFs (MuchPDF removed)
- [x] Unified `:SRC:` property across all media types
- [x] AssetPathResolver class for centralized path handling
- [x] PDF sizing probe standardized to 72 pt/in
- [x] `:FIT:` property accepted for all media (parser level)

---

## Milestone Overview

| Milestone | Focus | Duration | Priority | Dependencies |
|-----------|-------|----------|----------|--------------|
| **M1** | Intrinsic Size Providers | 1 week | **Critical** | None |
| **M2** | Media Renderer Abstraction | 1 week | **Critical** | M1 |
| **M3** | Cover/Contain FIT Unification | 1.5 weeks | **High** | M1, M2 |
| **M4** | Integration & Testing | 1 week | **High** | M1, M2, M3 |
| **M5** | PDF Pipeline Deprecations | 1 week | **Medium** | M4 |
| **M6** | Documentation & Examples | 1.5 weeks | **High** | M4, M5 |
| **Total** | | **8 weeks** | | |

---

## M1: Intrinsic Size Providers (Week 1)
**Goal**: Create unified interface for media dimension detection

### Overview
Extract size detection logic into provider classes following a common interface. Fix the critical SVG sizing bug by implementing proper viewBox parsing instead of assuming intrinsic size equals frame size.

### Tasks

#### M1.1: Foundation & Interface
- [ ] Create `src/pagemaker/generation/media_sizing.py`
- [ ] Define `IntrinsicSizeProvider` abstract base class
  ```python
  class IntrinsicSizeProvider(ABC):
      @abstractmethod
      def get_size_mm(self, src: str, **kwargs) -> Optional[Tuple[float, float]]:
          """Return (width_mm, height_mm) or None if indeterminate."""
          pass
  ```
- [ ] Add module-level docstring explaining provider pattern
- [ ] Create `tests/unit/test_media_sizing.py` test file

#### M1.2: PDF Size Provider (Wrapper)
- [ ] Implement `PdfSizeProvider` wrapping existing `pdf_intrinsic_size_mm`
- [ ] Support optional `box` parameter (media/crop/trim/bleed/art)
- [ ] Ensure consistent error handling (return `None` on failure)
- [ ] Add unit tests:
  - [ ] Valid PDF returns correct mm dimensions
  - [ ] Invalid path returns `None`
  - [ ] Box preference parameter respected

#### M1.3: SVG Size Provider (New Implementation)
- [ ] Implement `SvgSizeProvider.get_size_mm()`
  - [ ] Parse `viewBox` attribute using xml.etree.ElementTree
  - [ ] Fallback to `width`/`height` attributes if viewBox absent
  - [ ] Support common SVG units: px (default), pt, cm, mm, in, %
  - [ ] Default conversion: 96 DPI (1 SVG unit = 25.4/96 mm)
  - [ ] Handle malformed XML gracefully (return `None`)
- [ ] Create `tests/unit/test_svg_intrinsic_size.py`
  - [ ] Test viewBox parsing: `viewBox="0 0 200 100"`
  - [ ] Test unit conversion for all supported units
  - [ ] Test width/height fallback when no viewBox
  - [ ] Test percentage units (relative to parent, skip for now)
  - [ ] Edge cases: empty file, non-SVG XML, missing namespace
  - [ ] Verify mm conversion accuracy (±0.01mm tolerance)

#### M1.4: Raster Size Provider
- [ ] Implement `RasterSizeProvider.get_size_mm()`
  - [ ] Use PIL/Pillow to read image dimensions
  - [ ] Extract DPI from EXIF metadata or default to 96 DPI
  - [ ] Convert pixels to mm: `mm = px / dpi * 25.4`
  - [ ] Graceful degradation if PIL not installed (return `None`)
- [ ] Add unit tests:
  - [ ] PNG with DPI metadata
  - [ ] JPEG without DPI (assumes 96)
  - [ ] PIL unavailable scenario (mock import failure)
  - [ ] Corrupted image file

### Acceptance Criteria
- [ ] All three providers follow same interface contract
- [ ] SVG viewBox parsing works for standard formats
- [ ] Tests achieve 95%+ coverage on new module
- [ ] No regressions in existing PDF sizing tests
- [ ] Documentation includes usage examples

### Risks & Mitigation
**Risk**: SVG viewBox parsing may fail for complex/unusual formats  
**Mitigation**: Log warning and return `None`; fallback to frame-based sizing with deprecation notice

---

## M2: Media Renderer Abstraction (Week 2)
**Goal**: Extract 160 lines of duplicated rendering logic into strategy classes

### Overview
Replace type-specific if/elif branches in `generation/core.py:999-1162` with strategy pattern. Each media type gets a dedicated strategy class implementing common interface.

### Tasks

#### M2.1: Strategy Framework
- [ ] Create `src/pagemaker/generation/media_renderer.py`
- [ ] Define `RenderContext` dataclass:
  ```python
  @dataclass
  class RenderContext:
      element: dict
      page: dict
      area: dict
      padding_mm: Optional[dict]
      frame_w_mm: float
      frame_h_mm: float
      align: Optional[str]
      valign: Optional[str]
  ```
- [ ] Define `RenderedMedia` result dataclass
- [ ] Define `MediaRenderStrategy` abstract base class
  - [ ] `can_use_simple_path()` method
  - [ ] `render_simple()` method
  - [ ] `render_manual()` method
  - [ ] `render()` orchestration method
- [ ] Add comprehensive docstrings explaining strategy pattern

#### M2.2: Figure Render Strategy
- [ ] Implement `FigureRenderStrategy`
  - [ ] Simple path: delegates to Typst `image()` with fit parameter
  - [ ] Manual path: rarely needed, fallback to simple
  - [ ] Support caption rendering
  - [ ] Preserve existing `Fig()` macro wrapper behavior
- [ ] Create `tests/unit/test_figure_strategy.py`
  - [ ] Test contain/cover/stretch modes
  - [ ] Test alignment combinations
  - [ ] Test caption rendering
  - [ ] Verify output matches current implementation

#### M2.3: SVG Render Strategy
- [ ] Implement `SvgRenderStrategy` with size provider injection
  - [ ] Simple path: contain/stretch without alignment
  - [ ] Manual path: cover OR with alignment
  - [ ] **Fix**: Use `SvgSizeProvider` instead of frame size fallback
  - [ ] Support `:SCALE:` parameter multiplicatively
  - [ ] Implement clip block for cover overflow
- [ ] Create `tests/unit/test_svg_strategy.py`
  - [ ] **Critical test**: Verify 2:1 aspect SVG in square frame scales correctly
  - [ ] Test cover mode clipping
  - [ ] Test alignment offsets (place dx/dy)
  - [ ] Compare output to current implementation

#### M2.4: PDF Render Strategy
- [ ] Implement `PdfRenderStrategy` with size provider injection
  - [ ] Simple path: no alignment, use `PdfEmbed` macro
  - [ ] Manual path: with alignment, use `image()` with explicit mm
  - [ ] Support `:PAGE:` parameter
  - [ ] Support `:BOX:` preference parameter
  - [ ] Compute contain scale for PdfEmbed
- [ ] Create `tests/unit/test_pdf_strategy.py`
  - [ ] Test PdfEmbed path (no alignment)
  - [ ] Test manual path (with alignment)
  - [ ] Test cover mode clipping
  - [ ] Verify no regression vs current implementation

#### M2.5: Factory Function
- [ ] Implement `_get_media_renderer(element_type: str)` factory
- [ ] Wire up provider instances to strategies
- [ ] Add module-level cache for strategy instances (optimization)
- [ ] Test factory error handling for unknown types

### Acceptance Criteria
- [ ] Each strategy produces byte-identical Typst output to current implementation (snapshot tests)
- [ ] **SVG sizing bug fixed**: Alignment+cover mode uses proper intrinsic size
- [ ] All existing unit tests pass without modification
- [ ] 15+ new unit tests covering strategy edge cases
- [ ] Code coverage 90%+ on new module

### Risks & Mitigation
**Risk**: Strategy output differs from current implementation causing visual regressions  
**Mitigation**: Snapshot tests comparing old vs new output; beta testing period

---

## M3: Cover/Contain FIT Unification (Week 3-4)
**Goal**: Support true cover/contain/stretch semantics uniformly across all media types

### Overview
Currently PDFs are forcibly normalized to `contain` and SVGs lack proper cover support. Implement full cover semantics with alignment-based cropping for all media types.

### Tasks

#### M3.1: Parser Enhancements
- [ ] Remove PDF fit normalization code in `parser.py` (currently warns on non-contain)
- [ ] Accept `:FIT:` values `contain`, `cover`, `stretch` without warning for PDF
- [ ] Add `:CROP_BOX:` property for PDFs (values: media, crop, trim, bleed, art)
- [ ] Update tests expecting normalization warnings to accept new behavior
- [ ] Add parser test: `:FIT: cover` on PDF no longer warns

#### M3.2: Cover Math Implementation
- [ ] Verify `_compute_media_drawn_and_offsets()` in generator.py implements cover correctly
  - [ ] contain: scale = min(frame/intrinsic)
  - [ ] cover: scale = max(frame/intrinsic)
  - [ ] stretch: scale independently per axis
- [ ] Add unit tests: `tests/unit/test_cover_contain_math.py`
  - [ ] Cover: wide image in narrow frame (crop sides)
  - [ ] Cover: tall image in wide frame (crop top/bottom)
  - [ ] Cover with alignment (left/center/right offsets)
  - [ ] Edge case: zero-dimension intrinsic

#### M3.3: PDF Cover Support
- [ ] Update `PdfRenderStrategy.render_manual()` to support cover fit
- [ ] Implement clipping: `block(clip: true)[place(dx, dy)[image(...)]]`
- [ ] Test alignment anchors determine visible region:
  - [ ] Left: shows left edge of wide image
  - [ ] Center: shows center of wide image (default)
  - [ ] Right: shows right edge of wide image
- [ ] Create integration test: `tests/integration/test_pdf_cover_visual.py`
  - [ ] Compile actual PDF with cover fit
  - [ ] Verify clipping applied in Typst output
  - [ ] (Optional) Use pdfplumber to verify visual bounds

#### M3.4: SVG Cover Support
- [ ] Update `SvgRenderStrategy` to support cover (uses same math as PDF)
- [ ] Confirm Typst `image(fit: "cover")` behavior with SVGs
- [ ] If Typst auto-crops: use built-in, else: manual clip block
- [ ] Test alignment combinations (3 horizontal × 3 vertical = 9 cases)
- [ ] Create integration test: `tests/integration/test_svg_cover_visual.py`

#### M3.5: Alignment Offset Verification
- [ ] Document alignment-to-offset mapping in code comments
- [ ] Create visual test document: `examples/alignment_matrix.org`
  - [ ] 3×3 grid showing all alignment combinations
  - [ ] Same SVG in each cell with different alignment
  - [ ] Cover mode to show crop differences
- [ ] Compile and manually verify visual correctness

### Acceptance Criteria
- [ ] Users can specify `:FIT: cover` on pdf/svg without warnings
- [ ] Cover mode crops correctly based on alignment tokens
- [ ] All existing tests pass (zero regressions)
- [ ] 20+ new tests covering cover mode edge cases
- [ ] Visual verification document demonstrates alignment behavior

### Risks & Mitigation
**Risk**: Oversized content may not auto-clip in Typst  
**Mitigation**: Implement explicit `block(clip: true)` wrapper; test with actual compilation

---

## M4: Integration & Testing (Week 5)
**Goal**: Replace old rendering code, ensure zero regressions

### Overview
Wire up new abstractions in `generation/core.py`, remove old code, run comprehensive test suite.

### Tasks

#### M4.1: Core Integration
- [ ] Add `_get_media_renderer()` factory to `generation/core.py`
- [ ] Replace figure/svg/pdf if/elif branches (lines ~999-1162) with:
  ```python
  if el['type'] in ('figure', 'svg', 'pdf'):
      ctx = RenderContext(...)
      renderer = _get_media_renderer(el['type'])
      result = renderer.render(ctx, src, fit, **media_kwargs)
      content_fragments.append(result.typst_code)
  ```
- [ ] Ensure all `media_kwargs` (page, box, caption) passed correctly
- [ ] Update imports: add media_renderer, media_sizing modules

#### M4.2: Code Cleanup
- [ ] Delete old type-specific branches (~130 lines removed)
- [ ] Remove duplicated frame size computation code
- [ ] Remove duplicated alignment detection code
- [ ] Update `generation/elements.py` stub with comment referencing new location
- [ ] Run `pylint --duplicate-code` to verify reduction

#### M4.3: Regression Testing
- [ ] Run full existing test suite (200+ tests)
- [ ] Fix any integration issues that surface
- [ ] Add snapshot tests comparing Typst output before/after refactor
- [ ] Create `tests/integration/test_media_rendering.py`:
  - [ ] Compile document with all three media types
  - [ ] All three fit modes (contain/cover/stretch)
  - [ ] All alignment combinations
  - [ ] Verify PDF compiles without errors
  - [ ] (Optional) Verify visual layout with pdfplumber

#### M4.4: Performance Validation
- [ ] Profile rendering time before/after refactor
- [ ] Ensure <5% overhead from strategy dispatch
- [ ] Add caching to size providers if I/O bottleneck detected
- [ ] Document performance in commit message

### Acceptance Criteria
- [ ] Zero test regressions (all existing tests pass)
- [ ] Code size reduced by 100+ lines in core.py
- [ ] No measurable performance degradation
- [ ] Snapshot tests verify output equivalence
- [ ] Integration tests compile successfully

### Risks & Mitigation
**Risk**: Subtle behavioral changes cause hard-to-debug layout shifts  
**Mitigation**: Comprehensive snapshot testing; beta release with rollback flag

---

## M5: PDF Pipeline Deprecations (Week 6)
**Goal**: Deprecate legacy PDF sanitization/fallback pipeline

### Overview
PDF sanitization and SVG/PNG fallbacks are rarely needed with native Typst embedding. Move behind feature flag, emit deprecation warnings, document migration path.

### Tasks

#### M5.1: Extract Sanitization Helpers
- [ ] Move `_make_sanitized_copy()` from cli.py to `generation/pdf_processor.py`
- [ ] Move `_convert_pdf_to_svg()` from cli.py to `generation/pdf_processor.py`
- [ ] Move `_convert_pdf_to_png()` from cli.py to `generation/pdf_processor.py`
- [ ] Move `_apply_pdf_sanitized_copies()` from cli.py to `generation/pdf_processor.py`
- [ ] Move `_apply_pdf_svg_fallbacks()` from cli.py to `generation/pdf_processor.py`
- [ ] Update cli.py to import from pdf_processor

#### M5.2: Feature Flag & Deprecation
- [ ] Add `--legacy-pdf-fallbacks` CLI flag (replaces `--sanitize-pdfs`)
- [ ] Add `PAGEMAKER_ENABLE_PDF_FALLBACKS=1` environment variable override
- [ ] Default behavior: fallbacks **disabled**
- [ ] When enabled: emit `DeprecationWarning` on first use
- [ ] Update CLI help text explaining deprecation

#### M5.3: Documentation Updates
- [ ] Add deprecation notice to README
- [ ] Document external preprocessing alternatives:
  - [ ] Ghostscript for PDF repair
  - [ ] pdf2svg for manual SVG conversion
  - [ ] ImageMagick for rasterization
- [ ] Add troubleshooting section for problematic PDFs
- [ ] Update CHANGELOG with deprecation notice

#### M5.4: Test Updates
- [ ] Update `tests/integration/test_pdf_sanitize_fallback_cli.py` to use new flag
- [ ] Add test capturing deprecation warning
- [ ] Ensure tests pass both with and without flag

### Acceptance Criteria
- [ ] Sanitization code moved to pdf_processor.py
- [ ] Feature flag controls activation (default OFF)
- [ ] Deprecation warning emitted when used
- [ ] Documentation explains migration path
- [ ] Tests updated and passing

### Future Work (Phase 3 - Removal)
- [ ] Remove fallback conversion code entirely (v2.0)
- [ ] Remove integration test (v2.0)
- [ ] Re-measure intrinsic sizing if needed (v2.0)

---

## M6: Documentation & Examples (Week 7-8)
**Goal**: Comprehensive documentation for users and developers

### Overview
Document new abstractions, create examples demonstrating proper usage, write migration guide.

### Tasks

#### M6.1: API Documentation
- [ ] Add docstrings to all public classes/methods in media_sizing.py
- [ ] Add docstrings to all public classes/methods in media_renderer.py
- [ ] Document `IntrinsicSizeProvider` interface contract
- [ ] Document `MediaRenderStrategy` interface contract
- [ ] Add type hints throughout
- [ ] Generate API docs with sphinx (optional)

#### M6.2: Architecture Documentation
- [ ] Create `docs/architecture/media_rendering.md`:
  - [ ] Overview: problem statement, solution architecture
  - [ ] Diagram: Layer 1 (size providers) → Layer 2 (strategies) → Layer 3 (factory)
  - [ ] Strategy pattern rationale
  - [ ] How to add new media types
  - [ ] Size provider interface explained
  - [ ] Rendering decision tree (simple vs manual path)
  - [ ] Examples: implementing custom provider/strategy
- [ ] Add section to `docs/architecture/` README linking to media_rendering.md

#### M6.3: User Documentation
- [ ] Update README.md:
  - [ ] Unified Media Embedding section
  - [ ] `:FIT:` property documentation (contain/cover/stretch)
  - [ ] `:ALIGN:` and `:VALIGN:` interaction with fit modes
  - [ ] SVG sizing improvements note
  - [ ] Cover mode examples
- [ ] Update `examples/test_image_fit.org`:
  - [ ] Add SVG cover mode examples
  - [ ] Add alignment matrix demonstration
  - [ ] Add captions explaining each example
- [ ] Create `examples/svg_viewbox_demo.org`:
  - [ ] Demonstrate SVG sizing with various viewBox values
  - [ ] Show aspect ratio preservation
  - [ ] Include examples with and without alignment

#### M6.4: Migration Guide
- [ ] Create `docs/MIGRATION.md`:
  - [ ] Breaking changes (if any)
  - [ ] SVG sizing bug fix explanation (may shift layouts)
  - [ ] Deprecation timeline for `:PDF_SCALE_MODE:`
  - [ ] Deprecation timeline for PDF sanitization
  - [ ] How to opt into legacy behavior temporarily
  - [ ] Troubleshooting section for common issues
- [ ] Add release notes entry
- [ ] Update CHANGELOG.md

#### M6.5: Tutorial Content
- [ ] Create `examples/media_tutorial.org`:
  - [ ] Basic usage: single image with contain
  - [ ] Intermediate: PDF with cover and alignment
  - [ ] Advanced: SVG with custom viewBox and manual sizing
  - [ ] Troubleshooting: handling missing assets
- [ ] Add video walkthrough (optional, if resources permit)

### Acceptance Criteria
- [ ] 100% docstring coverage on public APIs
- [ ] Architecture doc with diagrams complete
- [ ] README updated with clear examples
- [ ] Migration guide addresses all breaking changes
- [ ] 3+ working examples demonstrating proper usage
- [ ] All documentation reviewed for clarity

---

## Cross-Cutting Concerns

### Testing Standards
All milestones must maintain:
- [ ] 90%+ code coverage on new modules
- [ ] Zero regressions in existing test suite (200+ tests)
- [ ] Integration tests with actual Typst compilation
- [ ] Snapshot tests for rendering output equivalence

### Code Quality Standards
- [ ] Type hints on all public APIs
- [ ] Docstrings following Google style
- [ ] Passes `pylint` with score ≥8.0
- [ ] Passes `mypy --strict` (optional, aspirational)
- [ ] Black formatting applied

### Performance Standards
- [ ] No measurable rendering time increase (<5% overhead)
- [ ] Size provider results cached per render pass
- [ ] Strategy instances reused (factory caching)

### Documentation Standards
- [ ] All public APIs documented
- [ ] Architecture decisions recorded
- [ ] Examples demonstrate real usage
- [ ] Migration path clear and actionable

---

## Success Metrics

### Quantitative
- [ ] Reduce `generation/core.py` media rendering from ~160 lines to ~30 lines (-80%)
- [ ] Zero regressions in 200+ existing tests
- [ ] 50+ new tests covering abstraction layer
- [ ] 90%+ coverage on new modules
- [ ] <5% performance overhead

### Qualitative
- [ ] **Critical Bug Fixed**: SVG alignment/cover sizing works correctly
- [ ] Consistent behavior across all media types (figure/svg/pdf)
- [ ] Clear architecture enables easy extension
- [ ] Excellent developer experience (docs, examples, tests)
- [ ] Smooth migration path for users

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking changes cause visual regressions | Medium | High | Snapshot tests, beta release, rollback flag |
| SVG viewBox parsing fails for edge cases | High | Medium | Comprehensive test suite, graceful fallback, warnings |
| Performance regression from abstraction | Low | Low | Profiling, caching, lazy loading |
| Incomplete size provider coverage | Medium | Medium | Return `None` when indeterminate, fallback strategy documented |
| Users rely on deprecated sanitization | Low | Medium | Clear deprecation timeline, external alternatives documented |

---

## Timeline & Dependencies

```
Week 1: M1 (Size Providers)
Week 2: M2 (Renderer Abstraction) ← depends on M1
Week 3: M3.1-M3.3 (Cover/Contain FIT) ← depends on M1, M2
Week 4: M3.4-M3.5 (Cover/Contain FIT continued)
Week 5: M4 (Integration & Testing) ← depends on M1, M2, M3
Week 6: M5 (PDF Deprecations) ← depends on M4
Week 7: M6.1-M6.3 (Documentation Part 1) ← depends on M4, M5
Week 8: M6.4-M6.5 (Documentation Part 2 + Polish)
```

**Total Duration**: 8 weeks  
**Critical Path**: M1 → M2 → M3 → M4 → M6  
**Parallel Work Possible**: M5 can proceed alongside M6

---

## Status Tracking

### Completed Milestones
- [x] **Legacy Cleanup**: MuchPDF removed, native Typst embedding
- [x] **Interface Unification**: `:SRC:` property, `:FIT:` parser support
- [x] **Asset Path Resolution**: AssetPathResolver class
- [x] **PDF Sizing Standard**: 72 pt/in probe default

### Current Milestone
- [ ] **M1**: Intrinsic Size Providers (In Progress)

### Upcoming
- [ ] **M2**: Media Renderer Abstraction
- [ ] **M3**: Cover/Contain FIT Unification
- [ ] **M4**: Integration & Testing
- [ ] **M5**: PDF Pipeline Deprecations
- [ ] **M6**: Documentation & Examples

---

## Approval & Sign-off

- [ ] Technical design reviewed
- [ ] Test strategy approved
- [ ] Timeline accepted (8 weeks)
- [ ] Risk assessment complete
- [ ] Resource allocation confirmed
- [ ] Ready to begin M1 implementation

---

## References

### Related Documents
- `docs/architecture/media_rendering.md` (to be created in M6)
- `docs/MIGRATION.md` (to be created in M6)
- `CHANGELOG.md` (update in M6)
- `README.md` (update in M6)

### Key Code Locations
- `src/pagemaker/parser.py:637-793` - Media IR generation
- `src/pagemaker/generation/core.py:999-1162` - Current rendering (to be replaced)
- `src/pagemaker/generation/pdf_processor.py` - PDF utilities
- `src/pagemaker/generation/media_sizing.py` - Size providers (to be created in M1)
- `src/pagemaker/generation/media_renderer.py` - Render strategies (to be created in M2)

### External Dependencies
- Typst (native PDF embedding)
- PIL/Pillow (optional, raster sizing)
- mutool (optional, PDF sanitization if enabled)

---

**End of Document**
