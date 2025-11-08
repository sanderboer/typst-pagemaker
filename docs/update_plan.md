# PDF Handling Modernization Plan

## Overview
Current PDF handling in pagemaker has legacy duplication and an overly complex fallback/sanitization pipeline living inside `cli.py`. The external `@preview/muchpdf` package previously used for PDF page embedding is now deprecated by Typst, which provides native PDF page embedding via the built-in `image()` function (`image("file.pdf", page: 1)`). Modernization goals:

- Adopt native Typst `image()` for PDF pages (remove `muchpdf` import/macro)
- Standardize intrinsic sizing to official PDF points (72 pt/in) conversion
- Remove duplicate sizing/cache implementations
- Keep automatic contain/cover scaling logic (already in `generation.core.process_pages`)
- Gradually deprecate PDF sanitization plus SVG/PNG fallbacks (make opt-in, then remove)
- Centralize any remaining PDF asset processing in `generation/pdf_processor.py`
- Preserve optional OutputIntent injection (post-process hook) – out of scope for first pass

## Current State
| Concern | Location(s) | Notes |
|---------|-------------|-------|
| Intrinsic size | `generator._pdf_intrinsic_size_mm` & `generation.pdf_processor.pdf_intrinsic_size_mm` | Duplicate logic + duplicate caches |
| Path adjustment | `generator.adjust_asset_paths` & `generation.pdf_processor.adjust_asset_paths` | Slight difference in how project root is resolved (parents[2] vs parents[3]) |
| Auto scale (contain/cover) | `generation.core.process_pages` | Imports size fn from `generator` only |
| Sanitization & fallbacks | Helper funcs embedded in `cli.py` (`_make_sanitized_copy`, `_convert_pdf_to_svg`, `_convert_pdf_to_png`, `_apply_pdf_sanitized_copies`, `_apply_pdf_svg_fallbacks`) | Not yet moved into `pdf_processor.py`; complicated; rarely needed with muchpdf |
| Tests depending on fallback | `tests/integration/test_pdf_sanitize_fallback_cli.py` | Ensures pipeline rewrites when `--sanitize-pdfs` supplied |

## Decisions
1. Canonical intrinsic sizing lives in `generation/pdf_processor.py` under public name `pdf_intrinsic_size_mm`.
2. Do not assume 72 pt/in; introduce a sizing probe and env override. Keep current behavior until validated by tests; move to spec or discovered effective value via probe.
3. Remove `muchpdf` import/macro usage; generate direct `image("...pdf", page: N)` calls. Provide optional env flag `PAGEMAKER_ENABLE_MUCHPDF_LEGACY=1` (temporary) to retain old macro for one minor release with deprecation warning.
4. Deprecate sanitize & fallback pipeline:
   - Stage 1: Feature flag (env or CLI) controls activation; default OFF; mark deprecated.
   - Stage 2: Emit `DeprecationWarning` when invoked; update docs with external preprocessing guidance.
   - Stage 3: Remove code & tests; keep migration note.
5. Centralize asset path discovery in a new `AssetPathResolver` class (`utils/assets_paths.py`) with a debug flag; refactor call sites to use it.
6. Update tests and documentation to assert native `image()` usage (no `#import "@preview/muchpdf"`).

## Tasks & Phases
### Phase 1 (This PR)
- [x] Unify intrinsic PDF sizing (alias + remove duplicate code block)
- [x] Implement `AssetPathResolver` class in `utils/assets_paths.py` with debug flag & caching
- [x] Refactor both existing `adjust_asset_paths` functions to thin wrappers calling resolver
- [ ] Introduce internal helper in `pdf_processor` for future sanitization hooks (no-op stub retained)
- [ ] Update `core.process_pages` to import size from `generation.pdf_processor` directly (optional early; alias already works)
- [ ] Add PDF sizing tests: contain and cover frames verify intended drawn size for a known MediaBox PDF (unit + optional integration compile)
- [ ] Add path resolution tests: resolution via PROJECT_ROOT, invocation CWD, source .org directory precedence, examples fallback, strict vs non-strict
- [ ] Document deprecation & migration plan in README / CLI help text

### Phase 2 (Subsequent PR)
- [ ] Extract sanitize + fallback helpers from `cli.py` into `pdf_processor` (still opt-in)
- [ ] Add `--legacy-pdf-fallbacks` CLI flag (replaces `--sanitize-pdfs`) + environment variable override `PAGEMAKER_ENABLE_PDF_FALLBACKS=1`
- [ ] Emit `DeprecationWarning` when invoked
- [ ] Adjust `test_pdf_sanitize_fallback_cli.py` to use new flag name

### Phase 3 (Removal)
- [ ] Remove fallback conversion code entirely
- [ ] Remove integration test & update docs
- [ ] Re-measure intrinsic sizing; adjust DPI constant if muchpdf guidance changes

## Acceptance Criteria (Phase 1)
- No duplicate intrinsic size functions; sizing probe scaffolding present
- AssetPathResolver class implemented; legacy functions delegate to it
- PDF sizing tests (contain/cover) pass for known-size PDF
- Path resolution tests (PROJECT_ROOT, CWD, source .org dir, examples fallback, strict mode) pass
- Tests updated to assert `image(` embedding (no `muchpdf` import)
- New plan file documents strategy & tasks
- (Temporary) legacy env flag path emits deprecation warning if used

## Test Plan
- PDF sizing tests
  - Fixture: use or generate a simple single-page PDF with MediaBox 612x792 pt (Letter) to have known ground truth.
  - Unit: compute frame sizes via layout helpers, get intrinsic PDF size via `pdf_intrinsic_size_mm`, and assert contain/cover scale leads to expected drawn width/height in mm.
  - Integration (optional): if Typst is available, compile a minimal document embedding the PDF at scale 1.0 inside frames sized to trigger contain/cover; verify resulting page content or vector bbox size within tolerance.
  - Parameterize tests for page index and explicit `scale` overrides to ensure logic holds.
  - Support env override `PAGEMAKER_PDF_PT_PER_IN` and a probe path for effective units/inch where available; assert test tolerances under both.
- Path resolution tests (AssetPathResolver)
  - CWD resolution: create a temp asset in the invocation working directory; ensure resolver rewrites to a path relative to `typst_dir`.
  - PROJECT_ROOT resolution: reference assets relative to repo root; ensure correct rewrite.
  - Source .org directory precedence: when provided to resolver, verify it is tried before project root.
  - Examples fallback: `assets/...` resolves under `examples/assets/...` when present.
  - Strict vs non-strict: in strict mode, non-existent sources are left unchanged; in non-strict, best-effort rewrite via project root is used.
  - Precedence assertion: CWD → source_dir → PROJECT_ROOT → typst_dir → examples fallback → best-effort.

## Milestones
- M1: AssetPathResolver skeleton, debug flag, and caching in place; both adjust functions delegate
- M2: Native image() embedding and legacy muchpdf flag path
- M3: Sizing probe utility and env override wiring; initial PDF sizing tests green
- M4: Path resolution tests green across precedence cases; docs updated
- M5: Deprecation of sanitize/fallbacks staged; readme and CLI help updated

## Risks / Follow-ups
- Changing DPI constant later can subtly shift layout; provide release note & optional override if needed.
- Removing sanitize/fallback may impact rare edge PDFs (encrypted/complex). Provide troubleshooting section recommending pre-processing with external tools (e.g., Ghostscript) if issues arise.

## TODO Annotations to Add
- Add `# TODO(pdf-dpi)` near DPI constant explaining revalidation step.
- Add `# TODO(deprecation)` comment where alias exists in `generator.py`.

## Migration Note (Draft)
Users should migrate from the deprecated `muchpdf` package to native Typst `image()` embedding immediately; pagemaker will remove the `muchpdf` import/macro after one minor release. Legacy `--sanitize-pdfs` & automatic SVG/PNG fallbacks are deprecated—preprocess problematic PDFs externally (e.g., Ghostscript) if needed. Upcoming versions will remove built-in fallbacks for a leaner pipeline.

## Status Update (2025-11-08)
- M2 implemented: native PdfEmbed macro uses image() with scale transform.
- Legacy MuchPDF retained only when `PAGEMAKER_ENABLE_MUCHPDF_LEGACY=1` (emits DeprecationWarning).
- Updated integration tests to drop hard MuchPDF requirement; legacy asset tests gated behind env flag.
- README updated to reflect native embedding + legacy flag.
- Next: finalize sizing probe (M3), move sanitize/fallbacks behind new flag (Phase 2), then deprecate/remove (Phase 3).
