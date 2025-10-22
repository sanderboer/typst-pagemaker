"""PDF processing and fallback handling."""

import math
import os
import pathlib
import re
from typing import Any, Dict

# Global cache for PDF size calculations
_pdf_size_cache: dict[str, tuple[float, float]] = {}


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
    # Convert points to mm with overrideable points-per-inch
    # Default remains 90.0 to match observed muchpdf behavior; override with env.
    # TODO(pdf-dpi): Revalidate this constant after migrating off muchpdf; may switch to 72 or probed value.
    # TODO(pdf-dpi): Revalidate this constant after migrating off muchpdf; may switch to 72 or probed value.
    try:
        pt_per_in = float(os.environ.get("PAGEMAKER_PDF_PT_PER_IN", "90"))
        if not math.isfinite(pt_per_in) or pt_per_in <= 0:
            pt_per_in = 90.0
    except Exception:
        pt_per_in = 90.0
    mm_per_pt = 25.4 / pt_per_in
    width_mm = width_pt * mm_per_pt
    height_mm = height_pt * mm_per_pt
    _pdf_size_cache[path] = (width_mm, height_mm)
    return width_mm, height_mm


def adjust_asset_paths(ir, typst_dir: pathlib.Path):
    """Adjust relative asset paths in IR to be relative to typst_dir.

    Delegates to AssetPathResolver for centralized behavior parity with generator.
    """
    try:
        from ..utils.assets_paths import AssetPathResolver
    except Exception:
        # Fallback to no-op if resolver import fails
        return
    resolver = AssetPathResolver(typst_dir=pathlib.Path(typst_dir))
    resolver.adjust_ir_asset_paths(ir)


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
