"""PDF processing and fallback handling."""

import math
import os
import pathlib
import re
from typing import Any, Dict

# Global cache for PDF size calculations
_pdf_size_cache = {}


def pdf_intrinsic_size_mm(path: str) -> tuple[float, float]:
    """Return (width_mm, height_mm) of first page of PDF by parsing MediaBox.
    Falls back to US Letter (612x792pt) when file missing/unreadable.
    Caches results per path for efficiency.
    """
    if not isinstance(path, str) or path == "":
        return 215.9, 279.4  # letter fallback
    if path in _pdf_size_cache:
        return _pdf_size_cache[path]
    width_pt, height_pt = 612.0, 792.0  # letter default
    try:
        if os.path.exists(path):
            # Read limited chunk to find /MediaBox [a b c d]
            with open(path, 'rb') as fh:
                data = fh.read(200_000)  # first 200KB usually enough
            # Decode forgivingly
            try:
                txt = data.decode('latin-1', errors='ignore')
            except Exception:
                txt = ''
            m = re.search(
                r'/MediaBox\s*\[\s*(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s*\]',
                txt,
            )
            if m:
                x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
                w = abs(x1 - x0)
                h = abs(y1 - y0)
                # Guard against zero/NaN
                if w > 1 and h > 1 and math.isfinite(w) and math.isfinite(h):
                    width_pt, height_pt = w, h
    except Exception:
        pass
    # Convert points (1/72") to mm
    # Empirical correction: muchpdf appears to render PDF user units ~90 per inch
    # rather than the traditional 72 pt/in. Observed embedded PDFs were ~0.8x
    # expected size (scale deficit of 1/1.25). Adjust conversion so intrinsic
    # size is smaller, yielding a larger auto-contain scale that fills frames.
    # When muchpdf clarifies its internal DPI, revisit this (possibly 96/in etc.).
    mm_per_pt = 25.4 / 90.0
    width_mm = width_pt * mm_per_pt
    height_mm = height_pt * mm_per_pt
    _pdf_size_cache[path] = (width_mm, height_mm)
    return width_mm, height_mm


def adjust_asset_paths(ir, typst_dir: pathlib.Path):
    """Adjust relative asset paths in IR to be relative to typst_dir."""
    try:
        typst_dir = typst_dir.resolve()
    except Exception:
        return
    # Determine project root relative to this module (../../)
    try:
        project_root = pathlib.Path(__file__).resolve().parents[3]  # Updated for generation/ subdir
    except Exception:
        project_root = pathlib.Path.cwd()

    def resolve_rel(src: str) -> str:
        if os.path.isabs(src) or re.match(r'^[a-zA-Z]+:', src):
            return src

        # If file exists relative to current working directory,
        # compute path relative to typst_dir (where .typ file will be)
        cwd_path = pathlib.Path.cwd() / src
        try:
            if cwd_path.resolve().exists():
                return os.path.relpath(cwd_path.resolve(), typst_dir)
        except Exception:
            pass

        # Try other candidates if not found in cwd
        candidates = [
            (project_root / src),
            (typst_dir / src),
        ]
        for cand in candidates:
            try:
                c = cand.resolve()
            except Exception:
                continue
            if c.exists():
                # Found existing file, rewrite relative to export dir
                try:
                    return os.path.relpath(c, typst_dir)
                except Exception:
                    continue

        # Special fallback: if user referenced 'assets/...', also look under examples/assets
        if src.startswith('assets/'):
            alt = project_root / 'examples' / src
            try:
                alt_res = alt.resolve()
                if alt_res.exists():
                    try:
                        return os.path.relpath(alt_res, typst_dir)
                    except Exception:
                        pass
            except Exception:
                pass

        # If no file found but src is relative, try best-effort path adjustment
        # relative to project root (common case for assets)
        if not os.path.isabs(src):
            try:
                project_asset_path = (project_root / src).resolve()
                return os.path.relpath(project_asset_path, typst_dir)
            except Exception:
                pass
        return src

    for page in ir.get('pages', []):
        for el in page.get('elements', []):
            fig = el.get('figure')
            if fig and fig.get('src'):
                fig['src'] = resolve_rel(fig['src'])
            pdf = el.get('pdf')
            if pdf and pdf.get('src'):
                pdf['src'] = resolve_rel(pdf['src'])
            svg = el.get('svg')
            if svg and svg.get('src'):
                svg['src'] = resolve_rel(svg['src'])


class PDFProcessor:
    """Handles PDF assets, sanitization, and fallback processing."""

    def __init__(self, export_dir: pathlib.Path):
        self.export_dir = export_dir

    def sanitize_pdf(self, pdf_path: pathlib.Path) -> bool:
        """Sanitize a PDF file for Typst compatibility."""
        # Placeholder - will be extracted from cli.py
        return True

    def convert_to_svg(
        self, pdf_path: pathlib.Path, output_path: pathlib.Path, page: int = 1
    ) -> bool:
        """Convert PDF page to SVG."""
        # Placeholder - will be extracted from cli.py
        return True

    def convert_to_png(
        self, pdf_path: pathlib.Path, output_path: pathlib.Path, page: int = 1
    ) -> bool:
        """Convert PDF page to PNG."""
        # Placeholder - will be extracted from cli.py
        return True


def sanitize_pdf_assets(ir: Dict[str, Any], export_dir: pathlib.Path) -> Dict[str, Any]:
    """Apply PDF sanitization to all PDF assets in IR."""
    # Placeholder - will be extracted from cli.py _apply_pdf_sanitized_copies
    return ir


def apply_pdf_fallbacks(ir: Dict[str, Any], export_dir: pathlib.Path) -> Dict[str, Any]:
    """Apply SVG/PNG fallbacks for problematic PDFs."""
    # Placeholder - will be extracted from cli.py _apply_pdf_svg_fallbacks
    return ir
